#!/usr/bin/env python3
"""
测试脚本：解析 RINEX 3.x 文件头，验证只提取各系统 L1 频率的 4 种观测类型
对于每个系统，提取：C1?(伪距), L1?(载波相位), D1?(多普勒), S1?(信噪比)
其中 ? 是各系统的 attribute (C/X/I/P/W 等)
"""
import re
import sys
from collections import defaultdict

def parse_rinex_header(filepath):
    """解析 RINEX 文件头，提取各系统观测类型"""
    obs_types = defaultdict(list)
    version = None
    
    with open(filepath, 'r') as f:
        for line in f:
            if 'RINEX VERSION' in line:
                version = float(line.strip().split()[0])
            if 'SYS / # / OBS TYPES' in line:
                # 格式: "G    16 C1C C2W C2X ... SYS / # / OBS TYPES"
                sys_char = line[0]
                # 提取 SYS 之前的观测类型部分,按空格分割
                types_part = line[:line.index('SYS')]
                # 去掉系统字符和数量,取后面的观测类型
                parts = types_part.split()
                # parts[0] = 系统字符, parts[1] = 数量, parts[2:] = 观测类型
                if len(parts) > 2:
                    types = parts[2:]
                else:
                    types = []
                if sys_char in obs_types:
                    obs_types[sys_char].extend(types)
                else:
                    obs_types[sys_char] = types
            if 'END OF HEADER' in line:
                break
    
    return version, obs_types

def get_l1_types_for_system(sys_char, all_types):
    """
    为每个系统提取 L1 频率的 4 种观测类型:
    - C1?: 伪距 (type=C, freq=1)
    - L1?: 载波相位 (type=L, freq=1)
    - D1?: 多普勒 (type=D, freq=1)
    - S1?: 信噪比 (type=S, freq=1)
    
    ? = attribute 字符，各系统可能不同:
    - GPS: C (C/A code)
    - GLO: C or P
    - GAL: X or C
    - BDS: I
    - QZS: C or X
    - SBS: C
    """
    l1_types = {0: None, 1: None, 2: None, 3: None}  # C, L, D, S
    type_map = {'C': 0, 'L': 1, 'D': 2, 'S': 3}
    
    for t in all_types:
        if len(t) < 3:
            continue
        obs_type = t[0]  # C, L, D, S
        freq_num = t[1]  # 1, 2, 5, 7, 8
        
        if freq_num != '1':
            continue
        if obs_type not in type_map:
            continue
        
        idx = type_map[obs_type]
        if l1_types[idx] is None:
            l1_types[idx] = t
        else:
            # 优先选择 C attribute (C/A code)
            # 其次 X, I, P, W
            priority = {'C': 1, 'X': 2, 'I': 3, 'P': 4, 'W': 5, 'A': 6, 'B': 7, 'Q': 8, 'Z': 9}
            old_attr = l1_types[idx][2] if len(l1_types[idx]) >= 3 else 'Z'
            new_attr = t[2] if len(t) >= 3 else 'Z'
            if priority.get(new_attr, 99) < priority.get(old_attr, 99):
                l1_types[idx] = t
    
    return l1_types

def parse_rinex_obs(filepath, target_types_per_sys, max_epochs=5):
    """
    解析 RINEX 观测数据，只提取目标观测类型的数据
    返回每个历元每个卫星的观测值
    """
    epochs = []
    current_epoch = None
    current_sat_idx = 0
    num_sats = 0
    sys_obs_count = {}  # 每个系统的观测类型偏移
    
    with open(filepath, 'r') as f:
        lines = f.readlines()
    
    i = 0
    in_header = True
    # 先解析头部获取各系统观测类型顺序
    all_sys_types = {}
    while i < len(lines):
        line = lines[i]
        if 'SYS / # / OBS TYPES' in line:
            sys_char = line[0]
            types_part = line[:line.index('SYS')]
            parts = types_part.split()
            if len(parts) > 2:
                types = parts[2:]
            else:
                types = []
            if sys_char in all_sys_types:
                all_sys_types[sys_char].extend(types)
            else:
                all_sys_types[sys_char] = types
        if 'END OF HEADER' in line:
            i += 1
            in_header = False
            break
        i += 1
    
    # 构建每个系统观测类型到列偏移的映射
    sys_type_offset = {}
    for sys_char, types in all_sys_types.items():
        type_offsets = {}
        for idx, t in enumerate(types):
            type_offsets[t] = idx
        sys_type_offset[sys_char] = type_offsets
    
    # 解析观测数据
    epoch_count = 0
    while i < len(lines) and epoch_count < max_epochs:
        line = lines[i].strip()
        
        if line.startswith('>'):
            # 新历元
            if current_epoch:
                epochs.append(current_epoch)
                epoch_count += 1
            parts = line.split()
            current_epoch = {
                'time': ' '.join(parts[1:7]),
                'sats': []
            }
            num_sats = int(parts[7]) if len(parts) > 7 else 0
            current_sat_idx = 0
            i += 1
            continue
        
        if not line or current_epoch is None:
            i += 1
            continue
        
        # 解析卫星数据
        sat_id = line[:3]
        sys_char = sat_id[0]
        
        sat_data = {'sat': sat_id, 'obs': {}}
        
        # 获取该系统在该 RINEX 文件中的观测类型列表
        sys_types = all_sys_types.get(sys_char, [])
        type_offsets = sys_type_offset.get(sys_char, {})
        
        # 获取目标类型
        target = target_types_per_sys.get(sys_char, {})
        
        # 每个观测类型占 14+1+2=17 字符 (ver 3.x) 或 14 字符 (ver 2.x)
        # RINEX 3.x: 14 chars value + 1 char LLI + 2 chars SNR
        field_width = 17  # for RINEX 3.x
        
        for target_type, obs_type_name in target.items():
            if obs_type_name is None:
                continue
            offset = type_offsets.get(obs_type_name, -1)
            if offset < 0:
                continue
            
            # 数据起始位置: 3 (sat) + offset * 17 (RINEX 3.x)
            # 但需要考虑换行情况（当观测类型超过一定数量时）
            data_offset = 3 + offset * field_width
            
            # 如果数据在当前行
            remaining = len(line) - 3
            needed = (offset + 1) * field_width
            
            if remaining >= needed:
                val_str = line[3 + offset * field_width : 3 + offset * field_width + 14].strip()
                if val_str:
                    try:
                        val = float(val_str)
                        sat_data['obs'][obs_type_name] = val
                    except ValueError:
                        pass
            else:
                # 数据可能在下一行
                if i + 1 < len(lines):
                    next_line = lines[i + 1].strip()
                    # 计算在下一行的偏移
                    types_per_line = 13  # RINEX 3.x 每行最多13个观测类型
                    next_offset = offset - types_per_line
                    if next_offset >= 0:
                        data_offset = next_offset * field_width
                        if len(next_line) > data_offset + 14:
                            val_str = next_line[data_offset: data_offset + 14].strip()
                            if val_str:
                                try:
                                    val = float(val_str)
                                    sat_data['obs'][obs_type_name] = val
                                except ValueError:
                                    pass
        
        current_epoch['sats'].append(sat_data)
        i += 1
    
    if current_epoch and epoch_count < max_epochs:
        epochs.append(current_epoch)
    
    return epochs

def main():
    rinex_file = '/home/mxl/workplace/ignav-debug/a-cpt/cpt0870.19o'
    
    print("=" * 80)
    print("RINEX 单频观测类型提取测试")
    print("=" * 80)
    
    # 1. 解析文件头
    version, obs_types = parse_rinex_header(rinex_file)
    print(f"\nRINEX 版本: {version}")
    print(f"\n各系统观测类型:")
    for sys_char in sorted(obs_types.keys()):
        print(f"  {sys_char}: {obs_types[sys_char]}")
    
    # 2. 为每个系统提取 L1 频率的 4 种观测类型
    print(f"\n{'=' * 80}")
    print("各系统 L1 频率提取的观测类型:")
    print(f"{'=' * 80}")
    
    target_types_per_sys = {}
    for sys_char, types in obs_types.items():
        l1_types = get_l1_types_for_system(sys_char, types)
        target_types_per_sys[sys_char] = l1_types
        
        type_names = {0: 'C1? (伪距)', 1: 'L1? (载波相位)', 2: 'D1? (多普勒)', 3: 'S1? (信噪比)'}
        print(f"\n  系统 {sys_char}:")
        for idx in range(4):
            t = l1_types[idx]
            if t:
                print(f"    {type_names[idx]}: {t}")
            else:
                print(f"    {type_names[idx]}: (不存在)")
    
    # 3. 解析前 5 个历元的观测数据
    print(f"\n{'=' * 80}")
    print("前 5 个历元的观测数据 (仅 L1 频率):")
    print(f"{'=' * 80}")
    
    epochs = parse_rinex_obs(rinex_file, target_types_per_sys, max_epochs=5)
    
    for i, epoch in enumerate(epochs):
        print(f"\n历元 {i+1}: {epoch['time']} ({len(epoch['sats'])} 颗卫星)")
        print(f"  {'卫星':<6} {'C1?(m)':<20} {'L1?(cycle)':<20} {'D1?(Hz)':<15} {'S1?(dBHz)':<10}")
        for sat in epoch['sats']:
            obs = sat['obs']
            c_val = f"{obs.get(target_types_per_sys.get(sat['sat'][0], {}).get(0, ''), 0):.3f}" if target_types_per_sys.get(sat['sat'][0], {}).get(0) and target_types_per_sys[sat['sat'][0]][0] in obs else "  ---"
            l_val = f"{obs.get(target_types_per_sys.get(sat['sat'][0], {}).get(1, ''), 0):.3f}" if target_types_per_sys.get(sat['sat'][0], {}).get(1) and target_types_per_sys[sat['sat'][0]][1] in obs else "  ---"
            d_val = f"{obs.get(target_types_per_sys.get(sat['sat'][0], {}).get(2, ''), 0):.3f}" if target_types_per_sys.get(sat['sat'][0], {}).get(2) and target_types_per_sys[sat['sat'][0]][2] in obs else "  ---"
            s_val = f"{obs.get(target_types_per_sys.get(sat['sat'][0], {}).get(3, ''), 0):.1f}" if target_types_per_sys.get(sat['sat'][0], {}).get(3) and target_types_per_sys[sat['sat'][0]][3] in obs else "  ---"
            print(f"  {sat['sat']:<6} {c_val:<20} {l_val:<20} {d_val:<15} {s_val:<10}")
    
    # 4. 验证提取结果
    print(f"\n{'=' * 80}")
    print("验证结果:")
    print(f"{'=' * 80}")
    
    all_ok = True
    for sys_char, l1_types in target_types_per_sys.items():
        missing = []
        for idx, t in l1_types.items():
            if t is None:
                type_names = {0: 'C1?', 1: 'L1?', 2: 'D1?', 3: 'S1?'}
                missing.append(type_names[idx])
        if missing:
            print(f"  系统 {sys_char}: 缺少 {', '.join(missing)}")
            all_ok = False
        else:
            print(f"  系统 {sys_char}: 完整提取 {[l1_types[i] for i in range(4)]}")
    
    if all_ok:
        print(f"\n  所有系统 L1 频率观测类型提取完整!")
    else:
        print(f"\n  部分系统缺少观测类型，但不影响处理 (缺失的类型值为 0)")

if __name__ == '__main__':
    main()
