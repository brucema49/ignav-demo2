"""ENU error evaluation script for ignav-debug/a-cpt cpt-rtdtc_gps runs.

Reads truth.csv and evaluates ignav-RTDTC-GPS output along with the existing
gipylib and ignav-RTKTC references. Produces statistics and time-series plots
using the same methodology as gipylib/data/plot/error-rslt(1).py.
"""
from __future__ import annotations

import csv
import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, TypedDict

import numpy as np
from scipy.interpolate import CubicHermiteSpline
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager
from datetime import datetime, timedelta
import time


try:
    from typing import NDArray
    Array = NDArray[Any]
except ImportError:
    Array = np.ndarray


PROJECT_ROOT = Path(__file__).resolve().parents[2]
ACPT_ROOT = PROJECT_ROOT / "a-cpt"

# ---- data paths ----
TRUTH_FILE = PROJECT_ROOT / ".." / "gipylib" / "data" / "truth.csv"
DEFAULT_EVAL = ACPT_ROOT / "output" / "rtdtcgps.rslt"

# ---- evaluation window (week + sow) ----
START_WEEK = 2046
START_SEC = 359000
END_WEEK = 2046
END_SEC = 359100
OUTPUT_FREQ = 100.0  # keep INS intermediate epochs at 100 Hz for Qins=2 rendering

GPS_EPOCH = datetime(1980, 1, 6, 0, 0, 0)


class StatEntry(TypedDict):
    name: str
    rmse: float
    max: float
    mean: float
    std: float
    percentile_95: float


def _configure_chinese_font() -> None:
    candidates = (
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Medium.ttc",
        "C:/Windows/Fonts/msyh.ttc",
        "/System/Library/Fonts/PingFang.ttc",
    )
    for candidate in candidates:
        font_path = Path(candidate)
        if font_path.is_file():
            font_manager.fontManager.addfont(str(font_path))
            plt.rcParams["font.family"] = [
                font_manager.FontProperties(fname=str(font_path)).get_name()
            ]
            return
    plt.rcParams["font.sans-serif"] = ["Noto Sans CJK SC", "Microsoft YaHei", "SimHei"]


_configure_chinese_font()
plt.rcParams["axes.unicode_minus"] = False


# --------- ECEF <-> LLH helpers ---------
def ecef2lla(x, y, z):
    a = 6378137.0
    f = 1 / 298.257223563
    b = a * (1 - f)
    e2 = 1 - (b / a) ** 2
    e2p = e2 / (1 - e2)
    lon = np.arctan2(y, x)
    p = np.sqrt(x ** 2 + y ** 2)
    theta = np.arctan2(z * a, p * b)
    lat = np.arctan2(z + e2p * b * np.sin(theta) ** 3,
                     p - e2 * a * np.cos(theta) ** 3)
    N = a / np.sqrt(1 - e2 * np.sin(lat) ** 2)
    h = p / np.cos(lat) - N
    return np.rad2deg(lat), np.rad2deg(lon), h


def lla2ecef_batch(lat_deg, lon_deg, h):
    a = 6378137.0
    e2 = 6.69437999014e-3
    lat = np.deg2rad(lat_deg)
    lon = np.deg2rad(lon_deg)
    sl, cl = np.sin(lat), np.cos(lat)
    N = a / np.sqrt(1 - e2 * sl * sl)
    x = (N + h) * cl * np.cos(lon)
    y = (N + h) * cl * np.sin(lon)
    z = (N * (1 - e2) + h) * sl
    return x, y, z


def ecef2lla_batch(x, y, z):
    n = len(x)
    lat = np.zeros(n)
    lon = np.zeros(n)
    h = np.zeros(n)
    for i in range(n):
        lat[i], lon[i], h[i] = ecef2lla(x[i], y[i], z[i])
    return lat, lon, h


# --------- Readers ---------
def read_ref_csv(filename: str) -> dict[str, Array] | None:
    print(f"读取真值文件 (CSV): {filename}")
    try:
        with open(filename, "r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
    except Exception as e:
        print(f"无法打开文件: {e}")
        return None
    if not rows:
        print("文件无有效数据")
        return None
    gps_week_list, gps_sec_list = [], []
    x_list, y_list, z_list = [], [], []
    dt_list = []
    for i, row in enumerate(rows):
        try:
            gps_week_list.append(float(row["week"]))
            gps_sec_list.append(float(row["sow"]))
            x_list.append(float(row["pos_x"]))
            y_list.append(float(row["pos_y"]))
            z_list.append(float(row["pos_z"]))
            dt_list.append(datetime.strptime(row["datetime"], "%Y-%m-%d %H:%M:%S.%f"))
        except (ValueError, KeyError, TypeError) as e:
            print(f"  跳过第 {i} 行: {e}")
            continue
    if not dt_list:
        print("没有有效数据行")
        return None
    data = {
        "datetime": np.array(dt_list, dtype=object),
        "x": np.array(x_list),
        "y": np.array(y_list),
        "z": np.array(z_list),
        "gps_week": np.array(gps_week_list),
        "gps_seconds": np.array(gps_sec_list),
    }
    print(f"成功读取 {len(dt_list)} 行真值数据")
    return data


def detect_pos_type(filename: str) -> str:
    """Auto-detect eval-file coordinate type from first data row magnitude."""
    with open(filename) as f:
        for ln in f:
            s = ln.strip()
            if not s or s.startswith("%"):
                continue
            nums = [float(x) for x in s.split()]
            if len(nums) >= 5 and (0 <= nums[0] < 4000) and (0 <= nums[1] <= 604800):
                c0, c1, c2 = nums[2], nums[3], nums[4]
            elif len(nums) >= 3:
                c0, c1, c2 = nums[0], nums[1], nums[2]
            else:
                continue
            # llh: lat in [-90,90], lon in [-180,180], height magnitude reasonable
            if abs(c0) <= 90.0 and abs(c1) <= 180.0 and abs(c2) < 1.0e4:
                return "llh"
            return "xyz"
    return "xyz"


def read_eval_file(filename: str, pos_type: str = "xyz",
                   ref_datetime: Array | None = None,
                   qins_col: int = 6) -> dict[str, Array] | None:
    if pos_type not in ("xyz", "llh"):
        raise ValueError(f"pos_type 必须是 'xyz' 或 'llh'，收到: {pos_type!r}")
    print(f"读取评价文件: {filename} [pos_type={pos_type}, qins_col={qins_col}]")
    try:
        with open(filename, "r") as f:
            lines = f.readlines()
    except Exception as e:
        print(f"无法打开文件: {e}")
        return None

    header_lines = [ln for ln in lines if ln.startswith("%")]
    has_qins = any("Qins" in ln for ln in header_lines) or len(header_lines) == 0

    valid = [ln.strip() for ln in lines if ln.strip() and not ln.startswith("%")]
    if not valid:
        print("文件无有效数据")
        return None

    first = [float(x) for x in valid[0].split()]
    has_time = len(first) >= 5 and (0 <= first[0] < 4000) and (0 <= first[1] <= 604800)

    lat, lon, height = [], [], []
    qins_list = []
    datetimes = []
    gps_week_list, gps_sec_list = [], []

    for ln in valid:
        parts = ln.split()
        if len(parts) < 3:
            continue
        try:
            nums = [float(p) for p in parts]
        except ValueError:
            continue
        if has_time:
            w, s = nums[0], nums[1]
            c0, c1, c2 = nums[2], nums[3], nums[4]
            if has_qins and len(nums) > qins_col:
                qins = int(nums[qins_col])
            else:
                qins = -1
            qins_list.append(qins)
            gps_week_list.append(w)
            gps_sec_list.append(s)
            datetimes.append(GPS_EPOCH + timedelta(seconds=w * 7 * 86400 + s))
        else:
            c0, c1, c2 = nums[0], nums[1], nums[2]
            qins_list.append(-1)
        if pos_type == "llh":
            la, lo, h = c0, c1, c2
        else:
            la, lo, h = ecef2lla(c0, c1, c2)
        lat.append(la)
        lon.append(lo)
        height.append(h)

    if not lat:
        print("没有有效数据行")
        return None

    if has_time:
        datetime_arr = np.array(datetimes, dtype=object)
        gps_week_arr = np.array(gps_week_list)
        gps_sec_arr = np.array(gps_sec_list)
        print(f"成功读取 {len(lat)} 行评价数据（pos_type={pos_type}，含 GPS 时间）")
    else:
        n = len(lat)
        if ref_datetime is not None and len(ref_datetime) >= 2:
            t0, t1 = ref_datetime[0], ref_datetime[-1]
            synth = [t0 + (t1 - t0) * (i / (n - 1)) for i in range(n)]
        else:
            synth = [GPS_EPOCH + timedelta(seconds=i) for i in range(n)]
        datetime_arr = np.array(synth, dtype=object)
        total = np.array([(dt - GPS_EPOCH).total_seconds() for dt in synth])
        gps_week_arr = np.floor(total / (7 * 86400)).astype(float)
        gps_sec_arr = total - gps_week_arr * 7 * 86400
        print(f"成功读取 {n} 行评价数据（pos_type={pos_type}，无时间列，已合成时间轴）")

    return {
        "datetime": datetime_arr,
        "lat": np.array(lat),
        "lon": np.array(lon),
        "height": np.array(height),
        "gps_week": gps_week_arr,
        "gps_seconds": gps_sec_arr,
        "qins": np.array(qins_list, dtype=int),
    }


# --------- Time filter / downsample ---------
def filter_data_by_gps_time(data: dict[str, Array],
                             start_week, start_sec,
                             end_week, end_sec) -> dict[str, Array]:
    def to_total(w, s):
        return w * 7 * 86400 + s

    mask = np.ones(len(data["datetime"]), dtype=bool)
    if start_week is not None and start_sec is not None:
        start_total = to_total(start_week, start_sec)
        data_total = data["gps_week"] * 7 * 86400 + data["gps_seconds"]
        mask &= (data_total >= start_total)
    if end_week is not None and end_sec is not None:
        end_total = to_total(end_week, end_sec)
        data_total = data["gps_week"] * 7 * 86400 + data["gps_seconds"]
        mask &= (data_total <= end_total)
    filtered = {k: data[k][mask] for k in data}
    print(f"  筛选后：{len(filtered['datetime'])} 行 (原 {len(data['datetime'])} 行)")
    return filtered


def downsample_to_freq(data: dict[str, Array], target_freq: float) -> dict[str, Array]:
    if len(data["datetime"]) < 2:
        return data
    dt = np.diff(data["datetime"])
    avg_interval = np.mean([d.total_seconds() for d in dt])
    current_freq = 1.0 / avg_interval if avg_interval > 0 else float("inf")
    if current_freq <= target_freq:
        return data
    factor = int(round(current_freq / target_freq))
    indices = np.arange(0, len(data["datetime"]), factor)
    down = {k: data[k][indices] for k in data}
    print(f"  降采样：{current_freq:.1f} Hz -> {target_freq:.1f} Hz，保留 {len(down['datetime'])} 点")
    return down


# --------- Smooth interpolation (truth -> eval epochs) ---------
def _estimate_smooth_derivative(t, y):
    t = np.asarray(t, dtype=np.float64); y = np.asarray(y, dtype=np.float64); n = len(t)
    if n == 1:
        return np.zeros_like(y)
    d = np.empty_like(y)
    d[0] = (y[1] - y[0]) / (t[1] - t[0])
    d[-1] = (y[-1] - y[-2]) / (t[-1] - t[-2])
    if n > 2:
        dt0 = t[1:-1] - t[:-2]; dt1 = t[2:] - t[1:-1]
        s0 = (y[1:-1] - y[:-2]) / dt0
        s1 = (y[2:] - y[1:-1]) / dt1
        dm = (dt1 * s0 + dt0 * s1) / (dt0 + dt1)
        d[1:-1] = np.clip(dm, np.minimum(s0, s1), np.maximum(s0, s1))
    return d


def _smooth_interpolate_ecef(ref_times, ref_xyz, eval_times):
    t = np.asarray(ref_times, dtype=np.float64)
    xyz = np.asarray(ref_xyz, dtype=np.float64)
    q = np.asarray(eval_times, dtype=np.float64)
    order = np.argsort(t, kind="stable"); t = t[order]; xyz = xyz[order]
    t, idx = np.unique(t, return_index=True); xyz = xyz[idx]
    if len(t) == 0:
        raise ValueError("真值数据为空")
    if np.any(q < t[0]) or np.any(q > t[-1]):
        raise ValueError("评价时间超出真值时间范围，无法平滑内插")
    if len(t) == 1:
        return np.repeat(xyz, len(q), axis=0)
    lat, lon, _ = ecef2lla(xyz[0, 0], xyz[0, 1], xyz[0, 2])
    lat = np.deg2rad(lat); lon = np.deg2rad(lon)
    sl, cl = np.sin(lat), np.cos(lat); so, co = np.sin(lon), np.cos(lon)
    dx, dy, dz = (xyz - xyz[0]).T
    enu = np.column_stack((-so * dx + co * dy,
                           -sl * co * dx - sl * so * dy + cl * dz,
                           cl * co * dx + cl * so * dy + sl * dz))
    if len(t) == 2:
        out = np.column_stack([np.interp(q, t, enu[:, i]) for i in range(3)])
    else:
        der = np.column_stack([_estimate_smooth_derivative(t, enu[:, i]) for i in range(3)])
        out = np.column_stack([CubicHermiteSpline(t, enu[:, i], der[:, i])(q) for i in range(3)])
    e, n, u = out.T
    return xyz[0] + np.column_stack((-so * e - sl * co * n + cl * co * u,
                                      co * e - sl * so * n + cl * so * u,
                                      cl * n + sl * u))


def match_ref_to_eval_interp(ref_data, eval_data):
    rt = np.array([dt.timestamp() for dt in ref_data["datetime"]], dtype=np.float64)
    et = np.array([dt.timestamp() for dt in eval_data["datetime"]], dtype=np.float64)
    valid = (et >= rt.min()) & (et <= rt.max())
    if not np.any(valid):
        print("评价时间完全不在真值时间范围内，无法匹配"); return None, None
    qins = eval_data.get("qins", np.full(len(et), -1, dtype=int))
    aligned = {
        "datetime": eval_data["datetime"][valid],
        "gps_week": eval_data.get("gps_week", np.full(len(et), np.nan))[valid],
        "gps_seconds": eval_data.get("gps_seconds", np.full(len(et), np.nan))[valid],
        "lat": eval_data["lat"][valid],
        "lon": eval_data["lon"][valid],
        "height": eval_data["height"][valid],
        "qins": qins[valid],
    }
    xyz = _smooth_interpolate_ecef(rt, np.column_stack((ref_data["x"], ref_data["y"], ref_data["z"])), et[valid])
    ref = {"datetime": aligned["datetime"], "x": xyz[:, 0], "y": xyz[:, 1], "z": xyz[:, 2]}
    print(f"  平滑内插得到 {len(xyz)} 个对齐点（真值 {len(np.unique(rt))} 个历元，C1 Hermite）")
    return ref, aligned


# --------- ENU error ---------
def calculate_enu_errors(ref_matched, eval_aligned):
    eval_x, eval_y, eval_z = lla2ecef_batch(eval_aligned["lat"],
                                             eval_aligned["lon"],
                                             eval_aligned["height"])
    dx = eval_x - ref_matched["x"]
    dy = eval_y - ref_matched["y"]
    dz = eval_z - ref_matched["z"]
    ref_lat, ref_lon, _ = ecef2lla_batch(ref_matched["x"], ref_matched["y"], ref_matched["z"])
    lat0_rad = np.deg2rad(ref_lat)
    lon0_rad = np.deg2rad(ref_lon)
    so, co = np.sin(lon0_rad), np.cos(lon0_rad)
    sl, cl = np.sin(lat0_rad), np.cos(lat0_rad)
    dE = -so * dx + co * dy
    dN = -sl * co * dx - sl * so * dy + cl * dz
    dU = cl * co * dx + cl * so * dy + sl * dz
    return {
        "datetime": ref_matched["datetime"],
        "gps_week": eval_aligned.get("gps_week", np.full(len(ref_matched["datetime"]), np.nan)),
        "gps_seconds": eval_aligned.get("gps_seconds", np.full(len(ref_matched["datetime"]), np.nan)),
        "e_error": dE,
        "n_error": dN,
        "u_error": dU,
        "hor_error": np.sqrt(dE ** 2 + dN ** 2),
        "threeD_error": np.sqrt(dE ** 2 + dN ** 2 + dU ** 2),
        "qins": eval_aligned.get("qins", np.full(len(ref_matched["datetime"]), -1, dtype=int)),
        "integer_update": integer_second_mask(
            eval_aligned.get("gps_seconds", np.full(len(ref_matched["datetime"]), np.nan))
        ),
    }


# --------- Stats ---------
def generate_error_statistics(results):
    qins = np.asarray(results.get("qins", np.full(len(results["datetime"]), -1, dtype=int)))
    mask, _ = primary_statistics_mask(qins)
    return generate_statistics_for_mask(results, mask)


def primary_statistics_mask(qins: np.ndarray) -> tuple[np.ndarray, str]:
    """Select the primary accuracy sample without hiding propagation epochs."""
    values = np.asarray(qins, dtype=int)
    if np.any(values == 8):
        return values == 8, "Qins=8 (tightly coupled update)"
    if np.any(values == 3):
        return values == 3, "Qins=3"
    if np.all(values < 0):
        return np.ones(values.shape, dtype=bool), "all valid epochs (Qins unavailable)"
    return values >= 0, "all reported Qins epochs (no Qins=3 updates)"


def integer_second_mask(gps_seconds: np.ndarray) -> np.ndarray:
    """Mark one nearest available epoch for each integer GPS second."""
    values = np.asarray(gps_seconds, dtype=float)
    selected = np.zeros(values.shape, dtype=bool)
    valid = np.flatnonzero(np.isfinite(values))
    if valid.size == 0:
        return selected
    order = valid[np.argsort(values[valid], kind="stable")]
    sorted_values = values[order]
    first = int(np.ceil(sorted_values[0] - 0.5))
    last = int(np.floor(sorted_values[-1] + 0.5))
    used: set[int] = set()
    for target in range(first, last + 1):
        right = min(int(np.searchsorted(sorted_values, target, side="left")), len(sorted_values) - 1)
        left = max(right - 1, 0)
        candidates = [left, right] if abs(sorted_values[left] - target) <= abs(sorted_values[right] - target) else [right, left]
        chosen = next((candidate for candidate in candidates if candidate not in used), None)
        if chosen is not None:
            used.add(chosen)
            selected[order[chosen]] = True
    return selected


def generate_statistics_for_mask(results, mask: np.ndarray):
    mask = np.asarray(mask, dtype=bool)
    mask &= np.isfinite(results["hor_error"])
    n_valid = int(np.count_nonzero(mask))
    if n_valid == 0:
        print("\n警告: 没有有效统计点，无法计算 RMS!")
        return {}
    stats = {}
    for key, name in [("e", "东方向"), ("n", "北方向"), ("u", "天方向"),
                      ("hor", "水平"), ("threeD", "三维")]:
        field = f"{key}_error"
        if field in results:
            err = results[field][mask]
            stats[key] = {
                "name": name,
                "rmse": float(np.sqrt(np.mean(err ** 2))),
                "max": float(np.max(np.abs(err))),
                "mean": float(np.mean(err)),
                "std": float(np.std(err)),
                "percentile_95": float(np.percentile(np.abs(err), 95)),
            }
    return stats


def qins_counts(qins: np.ndarray) -> dict[int, int]:
    values = np.asarray(qins, dtype=int)
    return {key: int(np.count_nonzero(values == key)) for key in (-1, 0, 2, 3, 8, 11)}


def classify_accuracy(horizontal_rmse: float, qins_counts: dict[int, int],
                      propagation_rmse: float, primary_count: int | None = None,
                      total_count: int | None = None,
                      primary_qins11_count: int = 0) -> dict[str, str | float]:
    total = sum(qins_counts.values())
    if total_count is not None:
        total = total_count
    update_count = primary_count if primary_count is not None else qins_counts.get(3, 0) + qins_counts.get(8, 0)
    update_fraction = update_count / total if total else 0.0
    qins11_fraction = primary_qins11_count / primary_count if primary_count else 0.0
    if primary_count and qins11_fraction >= 0.25:
        return {
            "category": "insufficient_gnss_updates",
            "update_fraction": update_fraction,
            "qins11_fraction_at_integer_seconds": qins11_fraction,
            "recommendation": "整数秒附近多数历元为卫星不足，先检查GPS/BDS星历覆盖、导航系统配置、截止高度角和基准/流动站观测对齐",
        }
    if primary_count is None and total and update_fraction < 0.10:
        return {
            "category": "insufficient_gnss_updates",
            "update_fraction": update_fraction,
            "qins11_fraction_at_integer_seconds": qins11_fraction,
            "recommendation": "检查时间对齐、卫星可用性、基站坐标和输入流格式，再调整滤波器权重",
        }
    if horizontal_rmse > 5.0 or horizontal_rmse > propagation_rmse * 2.0:
        return {
            "category": "noisy_or_misaligned_updates",
            "update_fraction": update_fraction,
            "qins11_fraction_at_integer_seconds": qins11_fraction,
            "recommendation": "优先核对杆臂/坐标系/IMU单位；随后逐项调整GNSS观测权重和INS过程噪声",
        }
    return {
        "category": "nominal",
        "update_fraction": update_fraction,
        "qins11_fraction_at_integer_seconds": qins11_fraction,
        "recommendation": "保留基线，使用同一时间窗比较候选参数",
    }


def build_summary_record(label: str, primary_stats: dict, all_stats: dict,
                         qins_counts: dict[int, int], primary_source: str,
                         diagnosis: dict) -> dict:
    def rmse(stats: dict, key: str) -> float:
        return float(stats.get(key, {}).get("rmse", float("nan")))

    return {
        "label": label,
        "primary_source": primary_source,
        "e_rmse_m": rmse(primary_stats, "e"),
        "n_rmse_m": rmse(primary_stats, "n"),
        "u_rmse_m": rmse(primary_stats, "u"),
        "horizontal_rmse_m": rmse(primary_stats, "hor"),
        "three_d_rmse_m": rmse(primary_stats, "threeD"),
        "all_epoch_horizontal_rmse_m": rmse(all_stats, "hor"),
        "qins_unknown_count": int(qins_counts.get(-1, 0)),
        "qins0_count": int(qins_counts.get(0, 0)),
        "qins2_count": int(qins_counts.get(2, 0)),
        "qins3_count": int(qins_counts.get(3, 0)),
        "qins8_count": int(qins_counts.get(8, 0)),
        "qins11_count": int(qins_counts.get(11, 0)),
        "integer_second_update_count": int(qins_counts.get("integer_second", 0)),
        "diagnosis_category": diagnosis.get("category", "unknown"),
        "integer_second_qins11_fraction": float(diagnosis.get("qins11_fraction_at_integer_seconds", float("nan"))),
        "diagnosis_recommendation": diagnosis.get("recommendation", ""),
    }


def print_statistics(stats, label, freq):
    print("\n" + "=" * 60)
    print(f"{label} ENU精度统计 (评价频率 {freq:.1f} Hz)")
    print("=" * 60)
    if not stats:
        print("无统计结果")
        print("=" * 60)
        return
    print(f"{'方向':<12} {'RMSE(m)':<10} {'Max(m)':<10} {'Mean(m)':<10} {'Std(m)':<10} {'95%分位(m)':<12}")
    print("-" * 64)
    for k in ["e", "n", "u", "hor", "threeD"]:
        if k in stats:
            s = stats[k]
            print(f"{s['name']:<12} {s['rmse']:<10.3f} {s['max']:<10.3f} {s['mean']:<10.3f} {s['std']:<10.3f} {s['percentile_95']:<12.3f}")
    print("=" * 60)


# --------- Plotting ---------
def plot_enu_error_time_series(results, stats, label, out_path):
    fig, axes = plt.subplots(3, 1, figsize=(12, 8))
    base_colors = ["#0072BD", "#D95319", "#77AC30"]
    qins_arr = np.asarray(results.get("qins", np.full(len(results["datetime"]), -1, dtype=int)))
    mask_qins0 = qins_arr == 0
    mask_qins2 = qins_arr == 2
    mask_qins3 = qins_arr == 3
    mask_qins8 = qins_arr == 8
    integer_updates = np.asarray(results.get("integer_update", np.zeros(len(qins_arr), dtype=bool)), dtype=bool)
    mask_none = qins_arr == -1

    for ax, (field, ylabel, key, color) in zip(axes,
                                                [("e_error", "东方向误差 (m)", "e", base_colors[0]),
                                                 ("n_error", "北方向误差 (m)", "n", base_colors[1]),
                                                 ("u_error", "天方向误差 (m)", "u", base_colors[2])]):
        data = results[field]
        dt = results["datetime"]
        if np.any(mask_none):
            ax.plot(dt[mask_none], data[mask_none], color=color, linewidth=0.6, alpha=0.7, label="有效历元")
        if np.any(mask_qins0):
            ax.scatter(dt[mask_qins0], data[mask_qins0], color=color, s=8, alpha=0.5, edgecolors="none", label="Qins=0")
        if np.any(mask_qins2):
            ax.scatter(dt[mask_qins2], data[mask_qins2], color="red", s=6, alpha=0.7, edgecolors="none",
                       marker=".", label="Qins=2(仅机械编排)")
        if np.any(mask_qins3):
            ax.scatter(dt[mask_qins3], data[mask_qins3], color="green", s=20, alpha=0.8, edgecolors="none",
                       label="Qins=3(量测更新)")
        if np.any(mask_qins8):
            ax.scatter(dt[mask_qins8], data[mask_qins8], color="purple", s=14, alpha=0.55, edgecolors="none",
                       label="Qins=8(紧组合更新)")
        if np.any(integer_updates):
            ax.scatter(dt[integer_updates], data[integer_updates], facecolors="none", edgecolors="black",
                       s=38, linewidths=0.8, label="整数秒评价点")
        ax.set_ylabel(ylabel, fontsize=11, fontweight="bold")
        ax.grid(True, linestyle="--", alpha=0.7)
        ymin, ymax = np.min(data), np.max(data)
        margin = (ymax - ymin) * 0.05 or 0.5
        ax.set_ylim(ymin - margin, ymax + margin)
        ax.legend(loc="upper left", fontsize=8, markerscale=1.2)
        if key in stats:
            ax.text(0.98, 0.95, f"RMS = {stats[key]['rmse']:.3f} m",
                    transform=ax.transAxes, fontsize=10,
                    verticalalignment="top", horizontalalignment="right",
                    bbox=dict(boxstyle="round", facecolor="wheat", alpha=0.5))
    axes[0].set_title(f"{label} ENU方向误差时间序列", fontsize=12, fontweight="bold")
    axes[-1].set_xlabel("时间", fontsize=11, fontweight="bold")
    fig.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=120, bbox_inches="tight")
    print(f"误差图已保存: {out_path}")
    plt.close(fig)


# --------- Full evaluation pipeline ---------
def evaluate_dataset(eval_file, pos_type, qins_col, label, out_dir, truth_file,
                     start_week, start_sec, end_week, end_sec, output_freq):
    ref_data = read_ref_csv(str(truth_file))
    if ref_data is None:
        return None, None
    eval_data = read_eval_file(str(eval_file), pos_type=pos_type,
                               ref_datetime=ref_data["datetime"], qins_col=qins_col)
    if eval_data is None:
        return None, None
    ref_data = filter_data_by_gps_time(ref_data, start_week, start_sec, end_week, end_sec)
    eval_data = filter_data_by_gps_time(eval_data, start_week, start_sec, end_week, end_sec)
    if len(ref_data["datetime"]) == 0 or len(eval_data["datetime"]) == 0:
        print(f"  筛选后数据为空，跳过 {label}")
        return None, None
    eval_data = downsample_to_freq(eval_data, output_freq)
    ref_matched, eval_aligned = match_ref_to_eval_interp(ref_data, eval_data)
    if ref_matched is None:
        return None, None
    results = calculate_enu_errors(ref_matched, eval_aligned)
    qins = np.asarray(results["qins"], dtype=int)
    primary_mask = np.asarray(results.get("integer_update", np.zeros(qins.shape, dtype=bool)), dtype=bool)
    primary_source = "nearest epoch to each integer GPS second"
    if not np.any(primary_mask):
        primary_mask, primary_source = primary_statistics_mask(qins)
    primary_stats = generate_statistics_for_mask(results, primary_mask)
    all_stats = generate_statistics_for_mask(results, np.ones(qins.shape, dtype=bool))
    counts = qins_counts(qins)
    propagation_mask = qins == 2
    propagation_stats = generate_statistics_for_mask(results, propagation_mask)
    propagation_rmse = float(propagation_stats.get("hor", {}).get("rmse", float("nan")))
    diagnosis = classify_accuracy(
        float(primary_stats.get("hor", {}).get("rmse", float("nan"))),
        counts,
        propagation_rmse,
        primary_count=int(primary_mask.sum()),
        total_count=len(qins),
        primary_qins11_count=int(np.count_nonzero(primary_mask & (qins == 11))),
    )
    print(f"\n统计样本: {int(primary_mask.sum())}/{len(qins)} 个 ({primary_source})")
    print(f"Qins计数: {counts}; 诊断: {diagnosis['category']}")
    print_statistics(primary_stats, label, output_freq)
    safe_label = label.replace(" ", "_").replace("/", "-")
    plot_enu_error_time_series(results, primary_stats, label, out_dir / f"error-{safe_label}.png")
    counts["integer_second"] = int(primary_mask.sum())
    record = build_summary_record(label, primary_stats, all_stats, counts, primary_source, diagnosis)
    return results, record


def write_summary(records: list[dict], out_dir: Path, args) -> None:
    if not records:
        return
    out_dir.mkdir(parents=True, exist_ok=True)
    csv_file = out_dir / "evaluation-summary.csv"
    with csv_file.open("w", encoding="utf-8", newline="") as fp:
        writer = csv.DictWriter(fp, fieldnames=list(records[0]))
        writer.writeheader()
        writer.writerows(records)
    json_file = out_dir / "evaluation-summary.json"
    with json_file.open("w", encoding="utf-8") as fp:
        json.dump(
            {
                "window": {"start_week": args.start_week, "start_sec": args.start_sec,
                           "end_week": args.end_week, "end_sec": args.end_sec},
                "output_frequency_hz": args.output_freq,
                "datasets": records,
            },
            fp,
            ensure_ascii=False,
            indent=2,
        )
    print(f"汇总已保存: {csv_file}")
    print(f"汇总已保存: {json_file}")


def parse_args():
    parser = argparse.ArgumentParser(description="Evaluate RTDTC-GPS output in an ENU truth frame.")
    parser.add_argument("--eval-file", type=Path, default=DEFAULT_EVAL)
    parser.add_argument("--truth-file", type=Path, default=TRUTH_FILE)
    parser.add_argument("--rtktc-file", type=Path, default=ACPT_ROOT / "output" / "rtktc.rslt")
    parser.add_argument("--gipylib-file", type=Path,
                        default=PROJECT_ROOT / ".." / "gipylib" / "data" / "output" / "rtdtc-gps-bds.rslt")
    parser.add_argument("--output-dir", type=Path, default=ACPT_ROOT / "plot")
    parser.add_argument("--start-week", type=float, default=START_WEEK)
    parser.add_argument("--start-sec", type=float, default=START_SEC)
    parser.add_argument("--end-week", type=float, default=END_WEEK)
    parser.add_argument("--end-sec", type=float, default=END_SEC)
    parser.add_argument("--output-freq", type=float, default=OUTPUT_FREQ)
    return parser.parse_args()


def main():
    args = parse_args()
    if (args.end_week, args.end_sec) < (args.start_week, args.start_sec):
        raise ValueError("结束 GPS 时间不能早于起始 GPS 时间")
    t0 = time.time()
    print("=" * 60)
    print("ignav RTDTC-GPS 评估脚本启动")
    print(f"时间窗口: GPS周{args.start_week:g} SOW {args.start_sec:g}-{args.end_sec:g}s")
    print("=" * 60)

    out_dir = args.output_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    records = []
    common = (out_dir, args.truth_file, args.start_week, args.start_sec,
              args.end_week, args.end_sec, args.output_freq)

    if args.eval_file.exists():
        eval_label = "ignav-RTDTC-GPS" if args.eval_file == DEFAULT_EVAL else f"ignav-RTDTC-GPS ({args.eval_file.stem})"
        eval_ptype = detect_pos_type(str(args.eval_file))
        _, record = evaluate_dataset(args.eval_file, eval_ptype, 6, eval_label, *common)
        if record is not None:
            records.append(record)
    else:
        print(f"[警告] 未找到ignav RTDTC输出: {args.eval_file}")

    # 2) 参考1: ignav-RTKTC 高精度解
    if args.rtktc_file.exists():
        _, record = evaluate_dataset(args.rtktc_file, "xyz", 6, "ignav-RTKTC-reference", *common)
        if record is not None:
            records.append(record)
    else:
        print(f"[提示] ignav-RTKTC参考未找到: {args.rtktc_file}")

    # 3) 参考2: gipylib RTDTC
    if args.gipylib_file.exists():
        _, record = evaluate_dataset(args.gipylib_file, "llh", 8, "gipylib-RTDTC-GPSBDS", *common)
        if record is not None:
            records.append(record)
    else:
        print(f"[提示] gipylib参考未找到: {args.gipylib_file}")

    # Summary table
    if records:
        print("\n" + "=" * 60)
        print("水平RMSE 汇总对比")
        print("=" * 60)
        print(f"{'方案':<28} {'E-RMSE(m)':<10} {'N-RMSE(m)':<10} {'U-RMSE(m)':<10} {'H-RMSE(m)':<10} {'3D-RMSE(m)':<10}")
        print("-" * 78)
        for record in records:
            print(f"{record['label']:<28} {record['e_rmse_m']:<10.3f} {record['n_rmse_m']:<10.3f} "
                  f"{record['u_rmse_m']:<10.3f} {record['horizontal_rmse_m']:<10.3f} {record['three_d_rmse_m']:<10.3f}")
        print("=" * 60)
        write_summary(records, out_dir, args)

    # Run trajectory plot
    print("\n绘制平面轨迹图...")
    try:
        import subprocess
        this_file = Path(__file__).resolve()
        subprocess.run([sys.executable, str(this_file.parent / "tra_neu.py"),
                        "--start-week", str(args.start_week), "--start-sec", str(args.start_sec),
                        "--end-week", str(args.end_week), "--end-sec", str(args.end_sec),
                        "--output-dir", str(out_dir)], check=True)
    except Exception as ex:
        print(f"  轨迹绘图调用失败: {ex}")

    elapsed = time.time() - t0
    print(f"\n全部评估完成，总耗时: {elapsed:.1f} 秒")
    print(f"图表输出目录: {out_dir}")


if __name__ == "__main__":
    main()
