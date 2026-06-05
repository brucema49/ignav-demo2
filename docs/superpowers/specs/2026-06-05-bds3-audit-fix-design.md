# BDS-3 适配代码修复设计

> 日期: 2026-06-05
> 来源: skills/bds3.md 审计报告（更新至当前工作树）
> 验证标准: 编译通过 + spp-tc.rslt ≥ 200000 行

## 已解决的旧问题

| 原编号 | 问题 | 状态 |
|--------|------|------|
| P0-1 | SNR 类型 `unsigned char` → `uint16_t` | 已修复（navlib.h + 所有驱动） |
| P0-2 | obscodes[] 扩展 | 已修复（rtkcmn.cc 60→69 项） |
| P2-4 | B1C+B2a 双频 IFLC | 已修复（pntpos.cc prange() B2a/B2b 分支） |
| P2-3 | pntpos.cc rescode() 添加 testsnr() | 已添加但被 `0&&` 禁用（重新归类为 P1） |

## 剩余修复

### P0 — 编译错误

**pntpos.cc:893 — 多出 `}`**

在 `pntpos()` 函数正常结束后 ( :892 )，第 893 行多出一个孤立的 `}`，导致编译错误。

操作：删除该行。

---

### P1 — 必须修复

**pntpos.cc:335 — testsnr() 被 `0&&` 禁用**

```
// 当前
if (0&&testsnr(0,0,azel[1+i*2],obs[i].SNR[0]*SNR_UNIT,&opt->snrmask)) continue;
// 改为
if (testsnr(0,0,azel[1+i*2],obs[i].SNR[0]*SNR_UNIT,&opt->snrmask)) continue;
```

影响：启用 SNR 掩码检查，低信噪比卫星被排除。SPP 定位质量更准确。

**rtkpos.cc:1192 — satexclude() var 硬编码为 0.0**

此问题跳过。`zdres()` 函数作用域内没有方差数组可用，`0.0` 是正确值——URA 检查在更早的处理环节 (pntpos.cc `rescode()`) 已完成。

**rtkcmn.cc:306 — BDS codepri 表缺少 D/P/Z**

当前 BDS 行：`{"IQX","IQX","IQX","IQX","IQX","",""}`

改为覆盖 BDS-3 信号：
| 频段 | 原值 | 新值 |
|------|------|------|
| L1/B1C | `"IQX"` | `"DPZXIQ"` |
| L2/B1I | `"IQX"` | `"DPZXIQ"` |
| L5/B2a | `"IQX"` | `"DPZXIQ"` |
| L6/B3I | `"IQX"` | `"DPZXIQ"` |
| L7/B2b | `"IQX"` | `"DPZXIQ"` |

优先级 D(数据) > P(导频) > Z(跟踪) > X > I > Q。

---

### P2 — 建议修复

**navlib.h: nav_t 清理废弃字段**

跳过。`leaps` 和 `glo_cpbias` 在代码库中有 50+ 处引用（接收机驱动、rinex、rtcm 等），移除需要大规模重构。

---

## 验证方案

### 编译
```bash
cd /home/mxl/workplace/ignav-debug/build
cmake .. && make -j$(nproc)
```

### 运行 (SPP-INS 紧组合)
```bash
./bin/navapp -s -o /home/mxl/workplace/ignav-debug/a-cpt/cpt.conf
```

- 程序持续运行直到手动终止 (Ctrl+C)
- SIGINT 处理函数 `sigshut()` 设置 `intflg=1` 触发优雅关闭

### 验收标准
- 编译无错误、无警告
- `wc -l /home/mxl/workplace/ignav-debug/a-cpt/spp-tc.rslt` ≥ 200000 行

### 行数预估

IMU 数据文件 `cpt_euroc.csv` 有 ~256k 行，程序以 `ins-hz=100` 输出。当前 spp-tc.rslt 仅 171k 行（程序在 ~67% 处崩溃/超时），修复后应能完整处理全部数据，天然达到 256k 行。

## 回归风险

1. SNR 掩码启用后可能减少可用卫星数，但更符合真实场景
2. codepri 优先级变化可能影响滤波初始化的卫星选择
3. `vare[i]` 替代 `0.0` 后可能增加卫星排除率，属于正确行为
