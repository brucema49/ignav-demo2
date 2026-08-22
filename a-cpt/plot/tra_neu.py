"""Plot truth, ignav-RTDTC, and gipylib-RTDTC horizontal trajectories (ENU).

Adapted from gipylib/data/plot/tra-neu.py for the ignav-debug/a-cpt workspace.
Uses ignav xyz-ecef output as truth reference trajectory overlay.
"""
from __future__ import annotations

import csv
import argparse
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager
import numpy as np


PROJECT_ROOT = Path(__file__).resolve().parents[2]
ACPT_ROOT = PROJECT_ROOT / "a-cpt"

# Evaluation window (GPS week 2046, seconds of week)
START_WEEK = 2046
START_SEC = 359095.0
END_WEEK = 2046
END_SEC = 359100.0

# Input files
IGNAV_RTDTC_FILE = ACPT_ROOT / "output" / "rtdtcgps.rslt"
IGNAV_RTKTC_FILE = ACPT_ROOT / "output" / "rtktc.rslt"
GIPYLIB_FILE = PROJECT_ROOT / ".." / "gipylib" / "data" / "output" / "rtdtc-gps-bds.rslt"
TRUTH_FILE = PROJECT_ROOT / ".." / "gipylib" / "data" / "truth.csv"

OUTPUT_FILE = ACPT_ROOT / "plot" / "tra-neu-rtdtcgps.png"

GPS_WEEK_SECONDS = 7.0 * 86400.0
WGS84_A = 6378137.0
WGS84_F = 1.0 / 298.257223563
WGS84_E2 = WGS84_F * (2.0 - WGS84_F)


def _configure_chinese_font() -> None:
    for candidate in (
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Medium.ttc",
        "C:/Windows/Fonts/msyh.ttc",
        "/System/Library/Fonts/PingFang.ttc",
    ):
        path = Path(candidate)
        if path.is_file():
            font_manager.fontManager.addfont(str(path))
            family = font_manager.FontProperties(fname=str(path)).get_name()
            plt.rcParams["font.family"] = [family]
            return
    plt.rcParams["font.sans-serif"] = ["Noto Sans CJK SC", "Microsoft YaHei", "SimHei"]


_configure_chinese_font()
plt.rcParams["axes.unicode_minus"] = False


def _total_seconds(week: np.ndarray, sow: np.ndarray) -> np.ndarray:
    return np.asarray(week, dtype=float) * GPS_WEEK_SECONDS + np.asarray(sow, dtype=float)


def _filter_window(time: np.ndarray, start_week: float = START_WEEK, start_sec: float = START_SEC,
                   end_week: float = END_WEEK, end_sec: float = END_SEC) -> np.ndarray:
    start = start_week * GPS_WEEK_SECONDS + start_sec
    end = end_week * GPS_WEEK_SECONDS + end_sec
    if start > end:
        raise ValueError("起始时间不能晚于结束时间")
    return np.flatnonzero((time >= start) & (time <= end))


def integer_second_indices(time: np.ndarray) -> np.ndarray:
    values = np.asarray(time, dtype=float)
    valid = np.flatnonzero(np.isfinite(values))
    if valid.size == 0:
        return np.empty(0, dtype=int)
    order = valid[np.argsort(values[valid], kind="stable")]
    sorted_time = values[order]
    first = int(np.ceil(sorted_time[0] - 0.5))
    last = int(np.floor(sorted_time[-1] + 0.5))
    selected = []
    used = set()
    for target in range(first, last + 1):
        right = int(np.searchsorted(sorted_time, target, side="left"))
        right = min(right, len(sorted_time) - 1)
        left = max(right - 1, 0)
        candidates = [left, right] if abs(sorted_time[left] - target) <= abs(sorted_time[right] - target) else [right, left]
        chosen = next((candidate for candidate in candidates if candidate not in used), None)
        if chosen is not None:
            used.add(chosen)
            selected.append(order[chosen])
    return np.asarray(selected, dtype=int)


def _lla_to_ecef(llh: np.ndarray) -> np.ndarray:
    lat, lon, height = np.deg2rad(llh[:, 0]), np.deg2rad(llh[:, 1]), llh[:, 2]
    sin_lat, cos_lat = np.sin(lat), np.cos(lat)
    n = WGS84_A / np.sqrt(1.0 - WGS84_E2 * sin_lat * sin_lat)
    return np.column_stack(
        ((n + height) * cos_lat * np.cos(lon),
         (n + height) * cos_lat * np.sin(lon),
         (n * (1.0 - WGS84_E2) + height) * sin_lat)
    )


def local_east_north(xyz: np.ndarray, origin_xyz: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    origin = np.asarray(origin_xyz, dtype=float)
    delta = np.asarray(xyz, dtype=float) - origin
    lon = np.arctan2(origin[1], origin[0])
    p = np.hypot(origin[0], origin[1])
    lat = np.arctan2(origin[2], p * (1.0 - WGS84_E2))
    for _ in range(5):
        n = WGS84_A / np.sqrt(1.0 - WGS84_E2 * np.sin(lat) ** 2)
        height = p / np.cos(lat) - n
        lat = np.arctan2(origin[2], p * (1.0 - WGS84_E2 * n / (n + height)))
    sin_lat, cos_lat, sin_lon, cos_lon = np.sin(lat), np.cos(lat), np.sin(lon), np.cos(lon)
    east = -sin_lon * delta[:, 0] + cos_lon * delta[:, 1]
    north = -sin_lat * cos_lon * delta[:, 0] - sin_lat * sin_lon * delta[:, 1] + cos_lat * delta[:, 2]
    return east, north


def _read_rows(filename: Path, columns: tuple[int, int, int], llh: bool,
               read_qins: bool = False, qins_col: int = 6) -> tuple[np.ndarray, np.ndarray, np.ndarray | None]:
    weeks, sow, positions, qins = [], [], [], []
    if not filename.exists():
        raise RuntimeError(f"文件不存在: {filename}")
    with filename.open("r", encoding="utf-8-sig", errors="replace") as fp:
        for line in fp:
            if not line.strip() or line.lstrip().startswith("%"):
                continue
            parts = line.split()
            try:
                week, second = float(parts[0]), float(parts[1])
                position = [float(parts[index]) for index in columns]
            except (ValueError, IndexError):
                continue
            weeks.append(week)
            sow.append(second)
            positions.append(position)
            if read_qins:
                try:
                    qins.append(int(float(parts[qins_col])))
                except (ValueError, IndexError):
                    qins.append(-1)
    if not positions:
        raise RuntimeError(f"没有有效数据: {filename}")
    xyz = _lla_to_ecef(np.asarray(positions)) if llh else np.asarray(positions, dtype=float)
    qins_array = np.asarray(qins, dtype=int) if read_qins else None
    return _total_seconds(np.asarray(weeks), np.asarray(sow)), xyz, qins_array


def read_truth(filename: Path) -> tuple[np.ndarray, np.ndarray, np.ndarray | None]:
    times, positions = [], []
    if not filename.exists():
        raise RuntimeError(f"真值文件不存在: {filename}")
    with filename.open("r", encoding="utf-8-sig", newline="") as fp:
        for row in csv.DictReader(fp):
            try:
                times.append(float(row["week"]) * GPS_WEEK_SECONDS + float(row["sow"]))
                positions.append([float(row["pos_x"]), float(row["pos_y"]), float(row["pos_z"])])
            except (KeyError, TypeError, ValueError):
                continue
    if not positions:
        raise RuntimeError(f"没有有效真值数据: {filename}")
    return np.asarray(times), np.asarray(positions, dtype=float), None


def _windowed(data: tuple[np.ndarray, np.ndarray, np.ndarray | None], window) -> tuple[np.ndarray, np.ndarray, np.ndarray | None]:
    indices = _filter_window(data[0], *window)
    if indices.size == 0:
        raise RuntimeError("指定时间段内没有数据")
    metadata = None if data[2] is None else data[2][indices]
    return data[0][indices], data[1][indices], metadata


def _safe_name(path: Path) -> str:
    return path.name


def plot_trajectories(datasets, output: Path, window) -> None:
    # Use the first valid truth set as origin
    origin = None
    windowed_list = []
    for name, data in datasets:
        try:
            w = _windowed(data, window)
            windowed_list.append((name, w))
            if origin is None and name == "真值":
                origin = w[1][0]
        except RuntimeError as e:
            print(f"  跳过 {name}: {e}")
            windowed_list.append((name, None))

    if origin is None:
        for name, w in windowed_list:
            if w is not None:
                origin = w[1][0]
                print(f"  使用 {name} 的第一个点作为 ENU 原点")
                break
    if origin is None:
        raise RuntimeError("所有数据集均无有效窗口数据")

    fig, ax = plt.subplots(figsize=(10, 8), dpi=160)
    color_cycle = ["green", "blue", "red", "orange", "purple", "brown"]

    for i, (name, w) in enumerate(windowed_list):
        if w is None:
            continue
        data_time, data_xyz, data_qins = w
        east, north = local_east_north(data_xyz, origin)
        color = color_cycle[i % len(color_cycle)]
        ax.plot(east, north, color=color, linewidth=0.8, alpha=0.8, label=name)
        if data_qins is not None and np.any(data_qins == 3):
            markers = np.flatnonzero(data_qins == 3)
        else:
            markers = integer_second_indices(data_time)
        ax.scatter(east[markers], north[markers], color=color, s=14, linewidths=0, zorder=3)

    ax.set_aspect("equal", adjustable="datalim")
    ax.set_xlabel("东向 East (m)", fontsize=11, fontweight="bold")
    ax.set_ylabel("北向 North (m)", fontsize=11, fontweight="bold")
    ax.set_title(f"RTDTC-GPS 平面轨迹对比 (GPS周{window[0]:g} SOW {window[1]:.0f}-{window[3]:.0f}s)",
                 fontsize=12, fontweight="bold")
    ax.grid(True, linestyle="--", linewidth=0.5, alpha=0.45)
    ax.legend(fontsize=10)
    fig.tight_layout()
    output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output, dpi=200)
    plt.close(fig)
    print(f"已输出轨迹图: {output}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Plot RTDTC trajectories in a truth-origin ENU frame.")
    parser.add_argument("--output-dir", type=Path, default=ACPT_ROOT / "plot")
    parser.add_argument("--truth-file", type=Path, default=TRUTH_FILE)
    parser.add_argument("--rtdtc-file", type=Path, default=IGNAV_RTDTC_FILE)
    parser.add_argument("--rtktc-file", type=Path, default=IGNAV_RTKTC_FILE)
    parser.add_argument("--gipylib-file", type=Path, default=GIPYLIB_FILE)
    parser.add_argument("--start-week", type=float, default=START_WEEK)
    parser.add_argument("--start-sec", type=float, default=START_SEC)
    parser.add_argument("--end-week", type=float, default=END_WEEK)
    parser.add_argument("--end-sec", type=float, default=END_SEC)
    args = parser.parse_args()
    if (args.end_week, args.end_sec) < (args.start_week, args.start_sec):
        raise ValueError("结束 GPS 时间不能早于起始 GPS 时间")
    window = (args.start_week, args.start_sec, args.end_week, args.end_sec)
    print("加载数据文件...")
    datasets = []

    # 1. 真值 (PVA truth from gipylib data)
    if args.truth_file.exists():
        truth = read_truth(args.truth_file)
        datasets.append(("真值", truth))
        print(f"  [OK] 真值: {_safe_name(TRUTH_FILE)} ({len(truth[0])} 点)")
    else:
        print(f"  [SKIP] 真值未找到: {args.truth_file}")

    # 2. ignav RTKTC (高精度参考, xyz ecef format, cols 2,3,4)
    if args.rtktc_file.exists():
        ignav_rtktc = _read_rows(args.rtktc_file, (2, 3, 4), llh=False, read_qins=True, qins_col=6)
        datasets.append(("ignav-RTKTC", ignav_rtktc))
        print(f"  [OK] ignav-RTKTC: {_safe_name(IGNAV_RTKTC_FILE)} ({len(ignav_rtktc[0])} 点)")
    else:
        print(f"  [SKIP] ignav-RTKTC 未找到: {args.rtktc_file}")

    # 3. ignav RTDTC-GPS (本次运行输出, xyz ecef format)
    if args.rtdtc_file.exists():
        ignav_rtdtc = _read_rows(args.rtdtc_file, (2, 3, 4), llh=False, read_qins=True, qins_col=6)
        datasets.append(("ignav-RTDTC-GPS", ignav_rtdtc))
        print(f"  [OK] ignav-RTDTC-GPS: {_safe_name(IGNAV_RTDTC_FILE)} ({len(ignav_rtdtc[0])} 点)")
    else:
        print(f"  [SKIP] ignav-RTDTC-GPS 未找到: {args.rtdtc_file}")

    # 4. gipylib RTDTC-GPS+BDS (llh format with lat/lon/height at cols 2,3,4)
    if args.gipylib_file.exists():
        gipylib = _read_rows(args.gipylib_file, (2, 3, 4), llh=True, read_qins=True, qins_col=8)
        datasets.append(("gipylib-RTDTC-GPSBDS", gipylib))
        print(f"  [OK] gipylib-RTDTC-GPSBDS: {_safe_name(GIPYLIB_FILE)} ({len(gipylib[0])} 点)")
    else:
        print(f"  [SKIP] gipylib-RTDTC 未找到: {args.gipylib_file}")

    if len(datasets) == 0:
        print("没有可绘制的数据集，退出")
        return

    plot_trajectories(datasets, args.output_dir / OUTPUT_FILE.name, window)


if __name__ == "__main__":
    main()
