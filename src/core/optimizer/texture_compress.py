#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""GPU texture compression engine with DDS and KTX2 container support.

Compresses RGBA images into block-compressed GPU formats (BC1–BC7,
ETC1/2, ASTC, PVRTC) and writes them into industry-standard DDS or
KTX2 container files, with optional mipmap generation.

Backends:
    * **etcpak** (pip) — BC1, BC3, ETC1, ETC2, and BC7 when available.
    * **astcenc** (CLI) — ASTC 4×4 / 6×6 / 8×8.
    * **PVRTexToolCLI** (CLI) — PVRTC 4bpp / 2bpp.

Usage:
    from core.optimizer.texture_compress import TextureCompressor
    from core.optimizer.constants import TextureFormat, TextureContainer

    compressor = TextureCompressor()
    compressor.compress_to_file(
        pil_image,
        output_path="atlas.dds",
        texture_format=TextureFormat.BC3,
        container=TextureContainer.DDS,
        generate_mipmaps=True,
    )
"""

from __future__ import annotations

import math
import shutil
import struct
import subprocess
import tempfile
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from PIL import Image

from core.optimizer.constants import TextureContainer, TextureFormat

# ---------------------------------------------------------------------------
# Backend availability detection
# ---------------------------------------------------------------------------

_etcpak = None
_etcpak_checked = False


def _ensure_etcpak():
    """Lazy-import etcpak; cached after first call."""
    global _etcpak, _etcpak_checked
    if not _etcpak_checked:
        try:
            import etcpak as _mod

            _etcpak = _mod
        except ImportError:
            _etcpak = None
        _etcpak_checked = True
    return _etcpak


def _find_cli_tool(name: str) -> Optional[str]:
    """Return the absolute path of *name* if found on PATH, else ``None``."""
    return shutil.which(name)


# ---------------------------------------------------------------------------
# Format → backend mapping
# ---------------------------------------------------------------------------

# etcpak function name lookup (resolved at compress time)
_ETCPAK_FUNCS: Dict[TextureFormat, str] = {
    TextureFormat.BC1: "compress_bc1",
    TextureFormat.BC3: "compress_bc3",
    TextureFormat.BC7: "compress_bc7",
    TextureFormat.ETC1: "compress_etc1_rgb",
    TextureFormat.ETC2_RGB: "compress_etc2_rgb",
    TextureFormat.ETC2_RGBA: "compress_etc2_rgba",
}

# Formats that need BGRA byte order for etcpak (ETC family)
_ETCPAK_BGRA_FORMATS = frozenset(
    {
        TextureFormat.ETC1,
        TextureFormat.ETC2_RGB,
        TextureFormat.ETC2_RGBA,
    }
)

# ASTC block dimensions
_ASTC_BLOCK_DIMS: Dict[TextureFormat, Tuple[int, int]] = {
    TextureFormat.ASTC_4x4: (4, 4),
    TextureFormat.ASTC_6x6: (6, 6),
    TextureFormat.ASTC_8x8: (8, 8),
}

# ---------------------------------------------------------------------------
# DDS constants
# ---------------------------------------------------------------------------

_DDS_MAGIC = b"DDS "

# DDS_HEADER.dwFlags
_DDSD_CAPS = 0x1
_DDSD_HEIGHT = 0x2
_DDSD_WIDTH = 0x4
_DDSD_PIXELFORMAT = 0x1000
_DDSD_MIPMAPCOUNT = 0x20000
_DDSD_LINEARSIZE = 0x80000

# DDS_PIXELFORMAT.dwFlags
_DDPF_FOURCC = 0x4

# DDS_HEADER.dwCaps
_DDSCAPS_COMPLEX = 0x8
_DDSCAPS_MIPMAP = 0x400000
_DDSCAPS_TEXTURE = 0x1000

# DXGI format values (for DX10 extended header)
_DXGI_FORMATS: Dict[TextureFormat, int] = {
    TextureFormat.BC1: 71,  # DXGI_FORMAT_BC1_UNORM
    TextureFormat.BC3: 77,  # DXGI_FORMAT_BC3_UNORM
    TextureFormat.BC7: 98,  # DXGI_FORMAT_BC7_UNORM
    TextureFormat.ETC1: 0,  # Not a DXGI format — use KTX2
    TextureFormat.ETC2_RGB: 0,
    TextureFormat.ETC2_RGBA: 0,
    TextureFormat.ASTC_4x4: 0,
    TextureFormat.ASTC_6x6: 0,
    TextureFormat.ASTC_8x8: 0,
    TextureFormat.PVRTC_4BPP: 0,
    TextureFormat.PVRTC_2BPP: 0,
}

# Legacy FourCC codes (BC1/BC3 can use these instead of DX10)
_FOURCC_CODES: Dict[TextureFormat, bytes] = {
    TextureFormat.BC1: b"DXT1",
    TextureFormat.BC3: b"DXT5",
}

# ---------------------------------------------------------------------------
# KTX2 constants
# ---------------------------------------------------------------------------

_KTX2_IDENTIFIER = bytes(
    [0xAB, 0x4B, 0x54, 0x58, 0x20, 0x32, 0x30, 0xBB, 0x0D, 0x0A, 0x1A, 0x0A]
)

# Vulkan VkFormat values
_VK_FORMATS: Dict[TextureFormat, int] = {
    TextureFormat.BC1: 131,  # VK_FORMAT_BC1_RGBA_UNORM_BLOCK
    TextureFormat.BC3: 137,  # VK_FORMAT_BC3_UNORM_BLOCK
    TextureFormat.BC7: 145,  # VK_FORMAT_BC7_UNORM_BLOCK
    TextureFormat.ETC1: 147,  # VK_FORMAT_ETC2_R8G8B8_UNORM_BLOCK (superset)
    TextureFormat.ETC2_RGB: 147,
    TextureFormat.ETC2_RGBA: 153,  # VK_FORMAT_ETC2_R8G8B8A8_UNORM_BLOCK
    TextureFormat.ASTC_4x4: 157,  # VK_FORMAT_ASTC_4x4_UNORM_BLOCK
    TextureFormat.ASTC_6x6: 165,  # VK_FORMAT_ASTC_6x6_UNORM_BLOCK
    TextureFormat.ASTC_8x8: 171,  # VK_FORMAT_ASTC_8x8_UNORM_BLOCK
    TextureFormat.PVRTC_4BPP: 1000054001,  # VK_FORMAT_PVRTC1_4BPP_UNORM_BLOCK_IMG
    TextureFormat.PVRTC_2BPP: 1000054000,  # VK_FORMAT_PVRTC1_2BPP_UNORM_BLOCK_IMG
}


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------


def check_format_available(texture_format: TextureFormat) -> Tuple[bool, str]:
    """Check whether the compression backend for *texture_format* is installed.

    Returns:
        ``(available, reason)`` — *reason* is empty when available, otherwise
        it describes what's missing.
    """
    if texture_format in _ETCPAK_FUNCS:
        mod = _ensure_etcpak()
        if mod is None:
            return False, "etcpak is not installed (pip install etcpak)"
        func_name = _ETCPAK_FUNCS[texture_format]
        if not hasattr(mod, func_name):
            return (
                False,
                f"etcpak does not expose {func_name} — update to latest version",
            )
        return True, ""

    if texture_format in _ASTC_BLOCK_DIMS:
        if (
            _find_cli_tool("astcenc")
            or _find_cli_tool("astcenc-avx2")
            or _find_cli_tool("astcenc-sse2")
        ):
            return True, ""
        return False, "astcenc CLI not found on PATH (download from arm.com)"

    if texture_format in (TextureFormat.PVRTC_4BPP, TextureFormat.PVRTC_2BPP):
        if _find_cli_tool("PVRTexToolCLI"):
            return True, ""
        return (
            False,
            "PVRTexToolCLI not found on PATH (download from imagination-technologies.com)",
        )

    return False, f"Unknown texture format: {texture_format.value}"


def check_container_supports_format(
    container: TextureContainer,
    texture_format: TextureFormat,
) -> Tuple[bool, str]:
    """Check whether *container* can hold *texture_format*.

    DDS only supports BC formats.  KTX2 supports everything.

    Returns:
        ``(supported, reason)``.
    """
    if container == TextureContainer.KTX2:
        return True, ""

    # DDS supports BC1, BC3, BC7 natively.
    # ETC/ASTC/PVRTC have no standard DDS representation.
    if container == TextureContainer.DDS:
        if texture_format in (TextureFormat.BC1, TextureFormat.BC3, TextureFormat.BC7):
            return True, ""
        return (
            False,
            f"DDS does not support {texture_format.value} — use KTX2 instead",
        )

    return False, f"Unknown container: {container.value}"


# ---------------------------------------------------------------------------
# Mipmap generation
# ---------------------------------------------------------------------------


def generate_mipmaps(image: Image.Image) -> List[Image.Image]:
    """Generate a full mipmap chain from *image*.

    Each level is half the previous dimensions (rounding down) until
    both dimensions reach 1.  Resampling uses Lanczos for quality.

    The first element of the returned list is the original *image*.
    """
    levels: List[Image.Image] = [image]
    w, h = image.size
    while w > 1 or h > 1:
        w = max(w // 2, 1)
        h = max(h // 2, 1)
        levels.append(image.resize((w, h), Image.LANCZOS))
    return levels


# ---------------------------------------------------------------------------
# Compression core
# ---------------------------------------------------------------------------


def _pad_to_block(image: Image.Image, block_w: int, block_h: int) -> Image.Image:
    """Pad *image* up to the next multiple of (block_w, block_h).

    Args:
        image: Source RGBA image to pad.
        block_w: Block width in pixels.
        block_h: Block height in pixels.

    Returns:
        A new image padded with transparent pixels, or the original
        if its dimensions are already block-aligned.
    """
    w, h = image.size
    new_w = math.ceil(w / block_w) * block_w
    new_h = math.ceil(h / block_h) * block_h
    if new_w == w and new_h == h:
        return image
    padded = Image.new("RGBA", (new_w, new_h), (0, 0, 0, 0))
    padded.paste(image, (0, 0))
    return padded


def _compress_etcpak(
    rgba_data: bytes,
    width: int,
    height: int,
    texture_format: TextureFormat,
) -> bytes:
    """Compress raw pixel data using etcpak.

    Args:
        rgba_data: Raw RGBA pixel bytes (4 bytes per pixel).
        width: Image width in pixels (must be block-aligned).
        height: Image height in pixels (must be block-aligned).
        texture_format: Target format (must be an etcpak-supported format).

    Returns:
        Compressed block data as bytes.
    """
    mod = _ensure_etcpak()
    if mod is None:
        raise RuntimeError("etcpak is not installed")

    func_name = _ETCPAK_FUNCS[texture_format]
    func = getattr(mod, func_name, None)
    if func is None:
        raise RuntimeError(f"etcpak.{func_name} not available")

    # ETC formats expect BGRA byte order
    if texture_format in _ETCPAK_BGRA_FORMATS:
        data = _rgba_to_bgra(rgba_data)
    else:
        data = rgba_data

    return func(data, width, height)


def _rgba_to_bgra(data: bytes) -> bytes:
    """Swap R and B channels in RGBA byte data.

    Args:
        data: Raw RGBA pixel bytes.

    Returns:
        A new bytes object with R and B channels swapped.
    """
    arr = bytearray(data)
    for i in range(0, len(arr), 4):
        arr[i], arr[i + 2] = arr[i + 2], arr[i]
    return bytes(arr)


def _compress_astc(
    image: Image.Image,
    texture_format: TextureFormat,
    quality: str = "medium",
) -> bytes:
    """Compress an image using astcenc CLI, returning raw ASTC block data.

    Args:
        image: RGBA PIL Image to compress.
        texture_format: One of the ASTC block-size formats.
        quality: astcenc quality preset (e.g. ``"fast"``, ``"medium"``,
            ``"thorough"``).

    Returns:
        Raw ASTC block data with the 16-byte file header stripped.

    Raises:
        RuntimeError: If astcenc is not found on PATH or the
            compression subprocess fails.
    """
    bx, by = _ASTC_BLOCK_DIMS[texture_format]

    # Find the astcenc binary
    for name in ("astcenc-avx2", "astcenc-sse2", "astcenc"):
        path = _find_cli_tool(name)
        if path:
            break
    else:
        raise RuntimeError("astcenc CLI not found on PATH")

    with tempfile.TemporaryDirectory(prefix="tatgf_astc_") as tmp:
        in_path = Path(tmp) / "input.png"
        out_path = Path(tmp) / "output.astc"
        image.save(str(in_path), "PNG")

        cmd = [
            path,
            "-cl",
            str(in_path),
            str(out_path),
            f"{bx}x{by}",
            "-{0}".format(quality),
        ]
        result = subprocess.run(
            cmd,
            capture_output=True,
            timeout=120,
            check=False,
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"astcenc failed (exit {result.returncode}): "
                f"{result.stderr.decode(errors='replace')}"
            )

        raw = out_path.read_bytes()
        # ASTC file header is 16 bytes — skip it to get raw block data
        if len(raw) <= 16:
            raise RuntimeError("astcenc produced empty output")
        return raw[16:]


def _compress_pvrtc(
    image: Image.Image,
    texture_format: TextureFormat,
) -> bytes:
    """Compress an image using PVRTexToolCLI, returning raw PVRTC data.

    Args:
        image: RGBA PIL Image to compress.
        texture_format: ``PVRTC_4BPP`` or ``PVRTC_2BPP``.

    Returns:
        Raw PVRTC block data with the 52-byte PVR3 header stripped.

    Raises:
        RuntimeError: If PVRTexToolCLI is not found on PATH or the
            compression subprocess fails.
    """
    bpp = "PVRTC1_4" if texture_format == TextureFormat.PVRTC_4BPP else "PVRTC1_2"
    tool = _find_cli_tool("PVRTexToolCLI")
    if not tool:
        raise RuntimeError("PVRTexToolCLI not found on PATH")

    with tempfile.TemporaryDirectory(prefix="tatgf_pvrtc_") as tmp:
        in_path = Path(tmp) / "input.png"
        out_path = Path(tmp) / "output.pvr"
        image.save(str(in_path), "PNG")

        cmd = [
            tool,
            "-i",
            str(in_path),
            "-o",
            str(out_path),
            "-f",
            bpp,
            "-q",
            "pvrtcnormal",
        ]
        result = subprocess.run(
            cmd,
            capture_output=True,
            timeout=120,
            check=False,
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"PVRTexToolCLI failed (exit {result.returncode}): "
                f"{result.stderr.decode(errors='replace')}"
            )

        raw = out_path.read_bytes()
        # PVR file header is 52 bytes (PVR3 format)
        if len(raw) <= 52:
            raise RuntimeError("PVRTexToolCLI produced empty output")
        return raw[52:]


def compress_level(
    image: Image.Image,
    texture_format: TextureFormat,
) -> Tuple[bytes, int, int]:
    """Compress a single mip level.

    Args:
        image: RGBA PIL Image (will be padded to block boundary).
        texture_format: Target GPU format.

    Returns:
        ``(compressed_bytes, padded_width, padded_height)``.
    """
    image = image.convert("RGBA")
    block = texture_format.block_size
    image = _pad_to_block(image, block, block)
    w, h = image.size

    if texture_format in _ETCPAK_FUNCS:
        data = _compress_etcpak(image.tobytes(), w, h, texture_format)
    elif texture_format in _ASTC_BLOCK_DIMS:
        data = _compress_astc(image, texture_format)
    elif texture_format in (TextureFormat.PVRTC_4BPP, TextureFormat.PVRTC_2BPP):
        data = _compress_pvrtc(image, texture_format)
    else:
        raise ValueError(f"Unsupported texture format: {texture_format.value}")

    return data, w, h


# ---------------------------------------------------------------------------
# DDS writer
# ---------------------------------------------------------------------------


def _compute_linear_size(width: int, height: int, fmt: TextureFormat) -> int:
    """Compute the byte size of one mip level's compressed data.

    Args:
        width: Mip level width in pixels.
        height: Mip level height in pixels.
        fmt: Texture format (provides block size and bytes-per-block).

    Returns:
        Total compressed size in bytes.
    """
    bw = max(1, math.ceil(width / fmt.block_size))
    bh = max(1, math.ceil(height / fmt.block_size))
    return bw * bh * fmt.block_bytes


def write_dds(
    compressed_levels: List[Tuple[bytes, int, int]],
    texture_format: TextureFormat,
    output_path: str,
) -> None:
    """Write a DDS file containing compressed mipmap data.

    Args:
        compressed_levels: List of ``(data, width, height)`` tuples,
            one per mip level (index 0 = largest).
        texture_format: The GPU compression format used.
        output_path: Destination file path.
    """
    if not compressed_levels:
        raise ValueError("No compressed data to write")

    _, base_w, base_h = compressed_levels[0]
    level_count = len(compressed_levels)
    linear_size = len(compressed_levels[0][0])

    use_dx10 = texture_format not in _FOURCC_CODES

    # --- DDS_HEADER flags ---
    flags = (
        _DDSD_CAPS | _DDSD_HEIGHT | _DDSD_WIDTH | _DDSD_PIXELFORMAT | _DDSD_LINEARSIZE
    )
    caps = _DDSCAPS_TEXTURE
    if level_count > 1:
        flags |= _DDSD_MIPMAPCOUNT
        caps |= _DDSCAPS_COMPLEX | _DDSCAPS_MIPMAP

    # --- DDS_PIXELFORMAT ---
    if use_dx10:
        pf_flags = _DDPF_FOURCC
        pf_fourcc = b"DX10"
        pf_rgb_bits = 0
        pf_rmask = pf_gmask = pf_bmask = pf_amask = 0
    else:
        pf_flags = _DDPF_FOURCC
        pf_fourcc = _FOURCC_CODES[texture_format]
        pf_rgb_bits = 0
        pf_rmask = pf_gmask = pf_bmask = pf_amask = 0

    pixelformat = struct.pack(
        "<II4sIIIII",
        32,  # dwSize
        pf_flags,
        pf_fourcc,
        pf_rgb_bits,
        pf_rmask,
        pf_gmask,
        pf_bmask,
        pf_amask,
    )

    reserved1 = b"\x00" * 44  # 11 DWORDs

    header = struct.pack(
        "<I I I I I I I",
        124,  # dwSize
        flags,
        base_h,
        base_w,
        linear_size,  # dwPitchOrLinearSize
        0,  # dwDepth
        level_count,  # dwMipMapCount
    )
    header += reserved1
    header += pixelformat
    header += struct.pack("<I I I I I", caps, 0, 0, 0, 0)

    # --- Optional DX10 header ---
    dx10 = b""
    if use_dx10:
        dxgi = _DXGI_FORMATS.get(texture_format, 0)
        if dxgi == 0:
            raise ValueError(
                f"DDS does not support {texture_format.value} — use KTX2 instead"
            )
        dx10 = struct.pack(
            "<I I I I I",
            dxgi,
            3,  # D3D10_RESOURCE_DIMENSION_TEXTURE2D
            0,  # miscFlag
            1,  # arraySize
            0,  # miscFlags2
        )

    with open(output_path, "wb") as f:
        f.write(_DDS_MAGIC)
        f.write(header)
        f.write(dx10)
        for data, _w, _h in compressed_levels:
            f.write(data)


# ---------------------------------------------------------------------------
# KTX2 writer
# ---------------------------------------------------------------------------


def write_ktx2(
    compressed_levels: List[Tuple[bytes, int, int]],
    texture_format: TextureFormat,
    output_path: str,
) -> None:
    """Write a KTX2 file containing compressed mipmap data.

    This writes a minimal spec-compliant KTX2 file (no supercompression,
    no key-value data, basic Data Format Descriptor).

    Args:
        compressed_levels: List of ``(data, width, height)`` tuples,
            one per mip level (index 0 = largest).
        texture_format: The GPU compression format used.
        output_path: Destination file path.
    """
    if not compressed_levels:
        raise ValueError("No compressed data to write")

    _, base_w, base_h = compressed_levels[0]
    level_count = len(compressed_levels)
    vk_format = _VK_FORMATS.get(texture_format, 0)

    # Build a minimal Data Format Descriptor (DFD).
    # The simplest valid DFD for a compressed format:
    #   totalSize (uint32) + basic descriptor block
    # We use 44 bytes for the basic descriptor block.
    dfd_block = struct.pack(
        "<"
        "I"  # vendorId (0) | descriptorType (0) | versionNumber (2)
        "H"  # descriptorBlockSize (24 + nSamples * 16, 1 sample = 40 bytes total)
        "B"  # colorModel: KHR_DF_MODEL_ETC1S=160 or just use a generic compressed model
        "B"  # colorPrimaries: KHR_DF_PRIMARIES_BT709=1
        "B"  # transferFunction: KHR_DF_TRANSFER_LINEAR=1
        "B"  # flags: KHR_DF_FLAG_ALPHA_STRAIGHT=0
        "BBBB"  # texelBlockDimension (bw-1, bh-1, 0, 0)
        "BBBBBBBB",  # bytesPlane[0-7]
        0x00020000,  # vendorId=0, descriptorType=0, versionNumber=2
        40,  # descriptorBlockSize
        _ktx2_color_model(texture_format),
        1,  # BT709
        1,  # linear
        0,  # alpha straight
        texture_format.block_size - 1,  # texelBlockDimension0
        texture_format.block_size - 1,  # texelBlockDimension1
        0,
        0,  # depth/pad
        texture_format.block_bytes,
        0,
        0,
        0,
        0,
        0,
        0,
        0,
    )
    # Add one sample descriptor (16 bytes)
    sample = struct.pack(
        "<HHIIII",
        0,  # bitOffset
        texture_format.block_bytes * 8 - 1,  # bitLength
        0,  # channelType + qualifiers
        0,  # samplePosition
        0,  # sampleLower
        0xFFFFFFFF,  # sampleUpper
    )
    dfd_block += sample
    dfd_total = struct.pack("<I", 4 + len(dfd_block)) + dfd_block

    # Level index — levels stored in decreasing size order (level 0 = largest)
    # Calculate offsets: header + level index + DFD
    header_size = 12 + 68  # identifier + header fields
    level_index_size = level_count * 24  # 3 uint64 per level
    dfd_offset = header_size + level_index_size
    dfd_size = len(dfd_total)

    # Data starts right after DFD (aligned to lcm(texel block size) but
    # we simplify to next 16-byte boundary)
    data_offset_base = dfd_offset + dfd_size
    data_offset_base = (data_offset_base + 15) & ~15  # align to 16

    # Compute per-level offsets
    level_entries: List[Tuple[int, int, int]] = []
    offset = data_offset_base
    for data, _w, _h in compressed_levels:
        size = len(data)
        level_entries.append((offset, size, size))
        # Align next level to 16 bytes
        offset += size
        offset = (offset + 15) & ~15

    # KTX2 header (68 bytes after identifier)
    ktx2_header = struct.pack(
        "<"
        "I"  # vkFormat
        "I"  # typeSize (1 for block-compressed)
        "I"  # pixelWidth
        "I"  # pixelHeight
        "I"  # pixelDepth
        "I"  # layerCount
        "I"  # faceCount
        "I"  # levelCount
        "I"  # supercompressionScheme
        "I"  # dfdByteOffset
        "I"  # dfdByteLength
        "I"  # kvdByteOffset
        "I"  # kvdByteLength
        "Q"  # sgdByteOffset
        "Q",  # sgdByteLength
        vk_format,
        1,  # typeSize
        base_w,
        base_h,
        0,  # pixelDepth (2D texture)
        0,  # layerCount (not array)
        1,  # faceCount (not cubemap)
        level_count,
        0,  # no supercompression
        dfd_offset,
        dfd_size,
        0,
        0,  # no key-value data
        0,
        0,  # no supercompression global data
    )

    # Write file
    with open(output_path, "wb") as f:
        f.write(_KTX2_IDENTIFIER)
        f.write(ktx2_header)

        # Level index
        for off, blen, ublen in level_entries:
            f.write(struct.pack("<QQQ", off, blen, ublen))

        # DFD
        f.write(dfd_total)

        # Padding to data start
        current = f.tell()
        if current < data_offset_base:
            f.write(b"\x00" * (data_offset_base - current))

        # Mip level data
        for i, (data, _w, _h) in enumerate(compressed_levels):
            f.write(data)
            # Pad to 16-byte boundary (except after last level)
            if i < level_count - 1:
                remainder = len(data) % 16
                if remainder:
                    f.write(b"\x00" * (16 - remainder))


def _ktx2_color_model(fmt: TextureFormat) -> int:
    """Return the KTX2 color model byte for a texture format.

    Args:
        fmt: The GPU compression format.

    Returns:
        KHR Data Format color model constant, or ``0`` if unknown.
    """
    if fmt in (TextureFormat.BC1, TextureFormat.BC3, TextureFormat.BC7):
        return 131  # KHR_DF_MODEL_BC1A / generic BC
    if fmt in (TextureFormat.ETC1, TextureFormat.ETC2_RGB, TextureFormat.ETC2_RGBA):
        return 160  # KHR_DF_MODEL_ETC1S
    if fmt in (TextureFormat.ASTC_4x4, TextureFormat.ASTC_6x6, TextureFormat.ASTC_8x8):
        return 162  # KHR_DF_MODEL_ASTC
    if fmt in (TextureFormat.PVRTC_4BPP, TextureFormat.PVRTC_2BPP):
        return 163  # KHR_DF_MODEL_PVRTC
    return 0


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


class TextureCompressor:
    """High-level GPU texture compression interface.

    Compresses PIL Images to block-compressed GPU formats and writes
    DDS or KTX2 container files with optional mipmap generation.

    Attributes:
        available_formats: Set of formats whose backends are installed.
    """

    def __init__(self) -> None:
        self._checked: Dict[TextureFormat, Tuple[bool, str]] = {}

    def is_available(self, texture_format: TextureFormat) -> Tuple[bool, str]:
        """Check whether *texture_format*'s backend is installed (cached)."""
        if texture_format not in self._checked:
            self._checked[texture_format] = check_format_available(texture_format)
        return self._checked[texture_format]

    @property
    def available_formats(self) -> List[TextureFormat]:
        """Return the list of formats whose backends are currently installed."""
        return [fmt for fmt in TextureFormat if self.is_available(fmt)[0]]

    def compress_to_file(
        self,
        image: Image.Image,
        output_path: str,
        texture_format: TextureFormat,
        container: TextureContainer,
        generate_mips: bool = False,
        progress_callback: Optional[callable] = None,
    ) -> str:
        """Compress *image* and write to *output_path*.

        Args:
            image: Source PIL Image (any mode — converted to RGBA internally).
            output_path: Destination file path (extension is replaced).
            texture_format: Target GPU compression format.
            container: DDS or KTX2.
            generate_mips: Whether to generate a full mipmap chain.
            progress_callback: Optional ``(current, total, message)`` callable.

        Returns:
            The actual output file path written (with correct extension).

        Raises:
            RuntimeError: If the backend is unavailable.
            ValueError: If the container doesn't support the format.
        """
        # Validate
        avail, reason = self.is_available(texture_format)
        if not avail:
            raise RuntimeError(reason)

        compat, reason = check_container_supports_format(container, texture_format)
        if not compat:
            raise ValueError(reason)

        image = image.convert("RGBA")

        # Generate mipmap chain
        if generate_mips:
            levels = generate_mipmaps(image)
        else:
            levels = [image]

        total = len(levels)
        compressed: List[Tuple[bytes, int, int]] = []

        for i, mip in enumerate(levels):
            if progress_callback:
                progress_callback(i, total, f"Compressing mip level {i + 1}/{total}")
            data, w, h = compress_level(mip, texture_format)
            compressed.append((data, w, h))

        if progress_callback:
            progress_callback(total, total, "Writing container file")

        # Determine output path with correct extension
        out = Path(output_path)
        ext = ".dds" if container == TextureContainer.DDS else ".ktx2"
        final_path = str(out.with_suffix(ext))

        if container == TextureContainer.DDS:
            write_dds(compressed, texture_format, final_path)
        else:
            write_ktx2(compressed, texture_format, final_path)

        return final_path

    def compress_bytes(
        self,
        image: Image.Image,
        texture_format: TextureFormat,
        generate_mips: bool = False,
    ) -> List[Tuple[bytes, int, int]]:
        """Compress *image* and return raw block data.

        Useful when you need the compressed bytes without writing a file
        (e.g., for embedding in a custom container).

        Args:
            image: Source PIL Image (any mode — converted to RGBA internally).
            texture_format: Target GPU compression format.
            generate_mips: Whether to generate a full mipmap chain.

        Returns:
            List of ``(compressed_bytes, width, height)`` per mip level.
        """
        avail, reason = self.is_available(texture_format)
        if not avail:
            raise RuntimeError(reason)

        image = image.convert("RGBA")
        levels = generate_mipmaps(image) if generate_mips else [image]
        return [compress_level(mip, texture_format) for mip in levels]


# ---------------------------------------------------------------------------
# KTX2 reader
# ---------------------------------------------------------------------------

# Reverse lookup: Vulkan VkFormat → TextureFormat
_VK_FORMAT_TO_TEXTURE: Dict[int, TextureFormat] = {v: k for k, v in _VK_FORMATS.items()}


def read_ktx2(path: str) -> Tuple[TextureFormat, int, int, bytes]:
    """Parse a KTX2 file and return the base mip level's compressed data.

    Only reads level 0 (the largest mip).  Supercompression is not
    supported — the file must contain raw block-compressed data.

    Args:
        path: Filesystem path to the KTX2 file.

    Returns:
        ``(texture_format, width, height, compressed_data)``

    Raises:
        ValueError: If the file is not a valid KTX2 or uses an
            unsupported VkFormat / supercompression scheme.
    """
    with open(path, "rb") as f:
        ident = f.read(12)
        if ident != _KTX2_IDENTIFIER:
            raise ValueError("Not a valid KTX2 file (bad identifier)")

        # KTX2 header: 68 bytes after identifier
        header_data = f.read(68)
        if len(header_data) < 68:
            raise ValueError("KTX2 header truncated")

        (
            vk_format,
            type_size,
            pixel_width,
            pixel_height,
            pixel_depth,
            layer_count,
            face_count,
            level_count,
            supercompression_scheme,
            dfd_offset,
            dfd_size,
            kvd_offset,
            kvd_size,
            sgd_offset,
            sgd_size,
        ) = struct.unpack("<IIIIIIIII II II QQ", header_data)

        if supercompression_scheme != 0:
            raise ValueError(
                f"KTX2 supercompression scheme {supercompression_scheme} "
                "is not supported (only uncompressed blocks are supported)"
            )

        texture_format = _VK_FORMAT_TO_TEXTURE.get(vk_format)
        if texture_format is None:
            raise ValueError(
                f"Unsupported KTX2 VkFormat {vk_format} — cannot determine "
                "texture compression format"
            )

        if level_count < 1:
            level_count = 1

        # Level index: one entry per level, each is 3× uint64
        # (byteOffset, byteLength, uncompressedByteLength)
        level_index_data = f.read(level_count * 24)
        if len(level_index_data) < 24:
            raise ValueError("KTX2 level index truncated")

        # Read level 0 (base mip)
        offset_0, length_0, _ubl_0 = struct.unpack("<QQQ", level_index_data[:24])

        f.seek(offset_0)
        compressed_data = f.read(length_0)

        if len(compressed_data) != length_0:
            raise ValueError(
                f"KTX2 level 0 data truncated: expected {length_0} bytes, "
                f"got {len(compressed_data)}"
            )

    return texture_format, pixel_width, pixel_height, compressed_data


# ---------------------------------------------------------------------------
# GPU texture decompression (texture2ddecoder)
# ---------------------------------------------------------------------------

_t2d = None
_t2d_checked = False


def _ensure_texture2ddecoder():
    """Lazy-import texture2ddecoder; cached after first call."""
    global _t2d, _t2d_checked
    if not _t2d_checked:
        try:
            import texture2ddecoder as _mod

            _t2d = _mod
        except ImportError:
            _t2d = None
        _t2d_checked = True
    return _t2d


# Mapping from TextureFormat to texture2ddecoder decode function name
# and whether the output is BGRA (True) or RGBA (False).
_T2D_DECODERS: Dict[TextureFormat, Tuple[str, bool]] = {
    TextureFormat.BC1: ("decode_bc1", True),
    TextureFormat.BC3: ("decode_bc3", True),
    TextureFormat.BC7: ("decode_bc7", True),
    TextureFormat.ETC1: ("decode_etc1", False),
    TextureFormat.ETC2_RGB: ("decode_etc2", False),
    TextureFormat.ETC2_RGBA: ("decode_etc2a8", False),
    # ASTC and PVRTC need special handling (extra params)
}


def decompress_to_image(
    compressed_data: bytes,
    width: int,
    height: int,
    texture_format: TextureFormat,
) -> Image.Image:
    """Decompress GPU-compressed block data to a PIL RGBA Image.

    Uses ``texture2ddecoder`` for all supported formats.

    Args:
        compressed_data: Raw block-compressed bytes.
        width: Image width in pixels (before block padding).
        height: Image height in pixels (before block padding).
        texture_format: The GPU compression format.

    Returns:
        PIL Image in RGBA mode.

    Raises:
        RuntimeError: If texture2ddecoder is not installed.
        ValueError: If the format is unsupported.
    """
    mod = _ensure_texture2ddecoder()
    if mod is None:
        raise RuntimeError(
            "texture2ddecoder is not installed — "
            "install it with: pip install texture2ddecoder"
        )

    # ASTC formats — need block width/height params
    if texture_format in _ASTC_BLOCK_DIMS:
        bw, bh = _ASTC_BLOCK_DIMS[texture_format]
        raw = mod.decode_astc(compressed_data, width, height, bw, bh)
        return Image.frombytes("RGBA", (width, height), raw)

    # PVRTC formats — need is2bpp flag
    if texture_format == TextureFormat.PVRTC_2BPP:
        raw = mod.decode_pvrtc(compressed_data, width, height, True)
        return Image.frombytes("RGBA", (width, height), raw)
    if texture_format == TextureFormat.PVRTC_4BPP:
        raw = mod.decode_pvrtc(compressed_data, width, height, False)
        return Image.frombytes("RGBA", (width, height), raw)

    # BC / ETC formats
    entry = _T2D_DECODERS.get(texture_format)
    if entry is None:
        raise ValueError(f"No decoder available for {texture_format.value}")

    func_name, is_bgra = entry
    func = getattr(mod, func_name, None)
    if func is None:
        raise ValueError(f"texture2ddecoder.{func_name} not found — update the package")

    raw = func(compressed_data, width, height)

    if is_bgra:
        # Convert BGRA → RGBA via NumPy
        import numpy as np

        arr = np.frombuffer(raw, dtype=np.uint8).reshape(height, width, 4).copy()
        arr[:, :, [0, 2]] = arr[:, :, [2, 0]]
        return Image.fromarray(arr, "RGBA")

    return Image.frombytes("RGBA", (width, height), raw)


def load_gpu_texture(path: str) -> Image.Image:
    """Load a DDS or KTX2 GPU-compressed texture as a PIL RGBA Image.

    For DDS files, delegates to Pillow's built-in DDS reader (supports
    BC1/BC3/BC7).  For KTX2 files, parses the container header and
    decompresses the base mip level using ``texture2ddecoder``.

    Args:
        path: Filesystem path to a ``.dds`` or ``.ktx2`` file.

    Returns:
        PIL Image in RGBA mode.

    Raises:
        ValueError: If the file extension is not ``.dds`` or ``.ktx2``.
        RuntimeError: If dependencies are missing.
    """
    ext = Path(path).suffix.lower()

    if ext == ".dds":
        img = Image.open(path)
        img.load()
        return img.convert("RGBA")

    if ext == ".ktx2":
        texture_format, w, h, data = read_ktx2(path)
        return decompress_to_image(data, w, h, texture_format)

    raise ValueError(f"Unsupported GPU texture extension: {ext}")
