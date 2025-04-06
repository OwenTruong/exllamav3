from __future__ import annotations
from typing_extensions import override
import torch
import torch.nn.functional as F
import numpy as np
from torch import nn
from ..models import Config
from . import Module
from .quant import LinearFP16, LinearFP16_torch, LinearEXL3
from .quant.exl3_lib import quantize_exl3
from ..ext import exllamav3_ext as ext
from ..conversion.allocation import allocate_linear
from ..util.memory import free_mem


class Linear(Module):

    def __init__(
        self,
        config: Config,
        key: str,
        in_features: int,
        out_features: int,
        qmap: str | None = None,
        alt_key: str | None = None,
        qbits_key: str = "bits",
        fkey : str | None = None,
        frange: tuple[int, int] | None = None,
        caps: dict = None,
        softcap: float = 0.0
    ):
        super().__init__(config, key, qmap)

        self.alt_key = alt_key
        self.in_features = in_features
        self.out_features = out_features
        self.inner = None
        self.qbits_key = qbits_key
        self.fkey = fkey
        self.frange = frange
        self.quant_type = None
        self.softcap = softcap

        if caps is not None:
            self.caps.update(caps)


    def load_fp16(self, key: str) -> bool:
        if self.config.stc.has_tensor_group(
            key,
            ["weight"]
        ):
            self.used_alt_key = key == self.alt_key
            weight = self.config.stc.get_tensor(key + ".weight", self.device)
            bias = self.config.stc.get_tensor(key + ".bias", self.device, optional = True)
            self.inner = LinearFP16(self.in_features, self.out_features, weight, bias)
            self.quant_type = "fp16"
            return True
        elif self.fkey and self.config.stc.has_tensor_group(
            self.fkey,
            ["weight"]
        ):
            weight = self.config.stc.get_tensor(self.fkey + ".weight", self.device)
            bias = self.config.stc.get_tensor(key + ".bias", self.device, optional = True)
            weight = weight[self.frange[0] : self.frange[1]].contiguous()
            if bias is not None:
                bias = bias[self.frange[0] : self.frange[1]].contiguous()
            self.inner = LinearFP16(self.in_features, self.out_features, weight, bias)
            self.quant_type = "fp16"
            return True
        return False


    def load_exl3(self, key: str) -> bool:
        if not self.config.stc.has_tensor_group(
            key,
            [["sv", "svh"], ["su", "suh"], "trellis"]
        ): return False
        self.used_alt_key = key == self.alt_key
        scale = self.config.stc.get_tensor(key + ".scale", self.device, optional = True)
        su = self.config.stc.get_tensor(key + ".su", self.device, optional = True)
        suh = self.config.stc.get_tensor(key + ".suh", self.device, optional = True)
        sv = self.config.stc.get_tensor(key + ".sv", self.device, optional = True)
        svh = self.config.stc.get_tensor(key + ".svh", self.device, optional = True)
        trellis = self.config.stc.get_tensor(key + ".trellis", self.device)
        bias = self.config.stc.get_tensor(key + ".bias", self.device, optional = True)
        self.inner = LinearEXL3(
            self.config,
            self.in_features,
            self.out_features,
            scale,
            su,
            sv,
            suh,
            svh,
            trellis,
            bias,
        )
        self.quant_type = "exl3"
        return True


    @override
    def load(self, device: torch.device):
        self.device = device
        keys = [self.key]
        if self.alt_key:
            keys += [self.alt_key]
        if any(self.load_exl3(k) for k in keys): return
        if any(self.load_fp16(k) for k in keys): return
        raise ValueError(f"No tensors found for {self.key} matching supported quantization format.")


    @override
    def unload(self):
        self.device = None
        self.inner = None


    @override
    def get_tensors(self):
        return self.inner.get_tensors(self.key)


    def convert_exl3(
        self,
        H_data: dict,
        quant_args: dict,
        progress_str: str | None = None,
        return_weight_q: bool = False,
        verbose: bool = False
    ):
        assert isinstance(self.inner, LinearFP16), \
            "Inner layer is already quant type"

        # Destroy original layer here to save VRAM, we only need weights
        orig_weight = self.inner.get_weight_tensor().float()
        orig_bias = self.inner.get_bias_tensor()
        self.inner = None

        weight_q, proxy_err, out_tensors = quantize_exl3(
            orig_weight,
            H_data,
            quant_args,
            return_weight_q,
            progress_str,
            verbose
        )

        self.inner = LinearEXL3(
            self.config,
            self.in_features,
            self.out_features,
            out_tensors.get("scale"),
            out_tensors.get("su"),
            out_tensors.get("sv"),
            out_tensors.get("suh"),
            out_tensors.get("svh"),
            out_tensors.get("trellis"),
            orig_bias
        )

        if return_weight_q:
            return proxy_err, weight_q
        else:
            return proxy_err


    def capture_H(self, x: torch.Tensor, params: dict):
        if self.qmap not in params["capture"]:
            params["capture"][self.qmap] = {
                "H": torch.zeros(self.in_features, self.in_features, dtype = torch.float32, device = self.device),
                "first_key": self.key,
                "count": 0,
                "finalized": False,
            }
        if params["capture"][self.qmap]["first_key"] == self.key:
            rows = np.prod(x.shape[:-1])
            dim = x.shape[-1]
            x = x.view((rows, dim)).to(torch.float, copy = True)

            params["capture"][self.qmap]["H"].addmm_(x.T, x)
            params["capture"][self.qmap]["count"] += rows


    @override
    def weights_numel(self):
        return self.in_features * self.out_features


    @override
    def forward(
        self,
        x: torch.Tensor,
        params: dict,
        out_dtype: torch.dtype | None = None,
    ) -> torch.Tensor:

        if "capture" in params and self.qmap:
            self.capture_H(x, params)

        x = self.inner.forward(x, params, out_dtype)
        if self.softcap != 0.0:
            ext.softcap(x, x, self.softcap)
        return x


    def allocate_q(self, quant_args: dict, surplus_bits: int):
        return allocate_linear(
            quant_args[self.qbits_key],
            surplus_bits,
            self
        )