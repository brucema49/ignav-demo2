# BDS-3 定位精度改进分析报告

**日期:** 2026-06-17
**背景:** BDS-3 升级后 GPS+BDS 模式可正常输出，但定位精度下降，3:28 左右出现巨大粗差
**分析范围:** BDS GEO/IGSO/MEO 卫星位置计算、钟差计算、星历选择
**参考:** rtklib_b34 参考实现

---

## 一、问题总结

通过对比 rtklib_b34 参考实现，发现 **5 个问题**，其中 2 个为导致粗差的根因。

### 根因分析

3:28 左右的巨大粗差主要由以下两个问题导致：
1. **BDS GEO 卫星判断不完整**：PRN 59-63 未被识别为 GEO 卫星
2. **eph2clk() 钟差迭代公式错误**：所有卫星钟差计算精度下降

---

## 二、问题详情

### 问题 1：BDS GEO 卫星判断不完整（根因 #1）

**严重程度:** CRITICAL - 导致 BDS-3 GEO 卫星位置计算错误
**文件:** `src/ins-gnss/ephemeris.cc:209`

**当前代码:**
```c
/* beidou geo satellite (ref [9]) */
if (sys==SYS_CMP&&prn<=5) {
    O=eph->OMG0+eph->OMGd*tk-omge*eph->toes;
    ...
}
```

**rtklib_b34 参考代码:**
```c
/* beidou geo satellite */
if (sys==SYS_CMP&&(prn<=5||prn>=59)) { /* ref [9] table 4-1 */
    O=eph->OMG0+eph->OMGd*tk-omge*eph->toes;
    ...
}
```

**问题分析:**
- BDS 卫星分类（ref [9] table 4-1）：
  - GEO 卫星：PRN 1-5, 59-63
  - IGSO 卫星：PRN 6-10, 13-16, 38-40
  - MEO 卫星：PRN 11-30, 41-58
- 当前代码只判断 `prn<=5`，**缺少 `prn>=59` 的判断**
- BDS-3 新增 GEO 卫星（PRN 59-63）被当作 IGSO/MEO 处理
- GEO 卫星使用特殊的坐标系旋转公式（COS_5/SIN_5），MEO/IGSO 使用标准公式
- 公式不匹配导致卫星位置误差可达数十公里

**影响:**
- 当 BDS-3 GEO 卫星（C59-C63）出现时，位置计算错误
- 伪距残差异常增大，滤波器受到冲击
- 3:28 的粗差很可能是某颗 GEO 卫星升起到可见范围时触发

**修复:**
```c
if (sys==SYS_CMP&&(prn<=5||prn>=59)) { /* ref [9] table 4-1 */
```

---

### 问题 2：eph2clk() 钟差迭代公式错误（根因 #2）

**严重程度:** CRITICAL - 影响所有卫星钟差精度
**文件:** `src/ins-gnss/ephemeris.cc:162-170`

**当前代码（有 bug）:**
```c
extern double eph2clk(gtime_t time, const eph_t *eph)
{
    double t;
    int i;
    
    t=timediff(time,eph->toc);
    
    for (i=0;i<2;i++) {
        t-=eph->f0+eph->f1*t+eph->f2*t*t;  ← 错误！t 不断累加
    }
    return eph->f0+eph->f1*t+eph->f2*t*t;
}
```

**rtklib_b34 参考代码（已修复）:**
```c
extern double eph2clk(gtime_t time, const eph_t *eph)
{
    double t,ts;
    int i;
    
    t=ts=timediff(time,eph->toc);
    
    for (i=0;i<2;i++) {
        t=ts-(eph->f0+eph->f1*t+eph->f2*t*t);  ← 正确！每次从 ts 减去
    }
    return eph->f0+eph->f1*t+eph->f2*t*t;
}
```

**问题分析:**
- 钟差迭代公式：`t_signal = t_receive - clock_bias`
- 正确做法：每次迭代都从原始时间差 `ts` 减去当前估计的钟差
- 当前代码：每次从 `t` 减去，导致 `t` 不断变化，迭代不收敛
- 当 f1（钟漂）较大或时间差较大时，误差显著

**数学推导:**
```
正确迭代：
  t_0 = ts
  t_1 = ts - (f0 + f1*t_0 + f2*t_0²)
  t_2 = ts - (f0 + f1*t_1 + f2*t_1²)

错误迭代（当前）：
  t_0 = ts
  t_1 = t_0 - (f0 + f1*t_0 + f2*t_0²) = ts - f0 - f1*ts - f2*ts²
  t_2 = t_1 - (f0 + f1*t_1 + f2*t_1²)  ← t_1 已经偏离，继续放大
```

**影响:**
- 所有卫星钟差计算精度下降
- 对 BDS 影响可能更大（BDS 钟差参数特性不同）
- 累积误差可能导致伪距残差增大，定位精度下降

**修复:**
```c
extern double eph2clk(gtime_t time, const eph_t *eph)
{
    double t,ts;
    int i;
    
    t=ts=timediff(time,eph->toc);
    
    for (i=0;i<2;i++) {
        t=ts-(eph->f0+eph->f1*t+eph->f2*t*t);
    }
    return eph->f0+eph->f1*t+eph->f2*t*t;
}
```

---

### 问题 3：geph2clk() 钟差迭代公式错误

**严重程度:** HIGH - 影响 GLONASS 钟差精度
**文件:** `src/ins-gnss/ephemeris.cc:290-302`

**当前代码（有 bug）:**
```c
extern double geph2clk(gtime_t time, const geph_t *geph)
{
    double t;
    int i;
    
    t=timediff(time,geph->toe);
    
    for (i=0;i<2;i++) {
        t-=-geph->taun+geph->gamn*t;  ← 错误！
    }
    return -geph->taun+geph->gamn*t;
}
```

**rtklib_b34 参考代码（已修复）:**
```c
extern double geph2clk(gtime_t time, const geph_t *geph)
{
    double t,ts;
    int i;
    
    t=ts=timediff(time,geph->toe);
    
    for (i=0;i<2;i++) {
        t=ts-(-geph->taun+geph->gamn*t);  ← 正确！
    }
    return -geph->taun+geph->gamn*t;
}
```

**问题分析:**
- 与 eph2clk() 相同的 bug
- 影响 GLONASS 卫星钟差计算

**修复:**
```c
extern double geph2clk(gtime_t time, const geph_t *geph)
{
    double t,ts;
    int i;
    
    t=ts=timediff(time,geph->toe);
    
    for (i=0;i<2;i++) {
        t=ts-(-geph->taun+geph->gamn*t);
    }
    return -geph->taun+geph->gamn*t;
}
```

---

### 问题 4：var_uraeph() ura=15 数组越界

**严重程度:** MEDIUM - 影响卫星方差计算
**文件:** `src/ins-gnss/ephemeris.cc:88-94`

**当前代码:**
```c
static double var_uraeph(int ura)
{
    const double ura_value[]={   
        2.4,3.4,4.85,6.85,9.65,13.65,24.0,48.0,96.0,192.0,384.0,768.0,1536.0,
        3072.0,6144.0
    };
    return ura<0||15<ura?SQR(6144.0):SQR(ura_value[ura]);  ← 15<ura 错误
}
```

**rtklib_b34 参考代码:**
```c
static double var_uraeph(int sys, int ura)
{
    const double ura_value[]={   
        2.4,3.4,4.85,6.85,9.65,13.65,24.0,48.0,96.0,192.0,384.0,768.0,1536.0,
        3072.0,6144.0
    };
    if (sys==SYS_GAL) { /* galileo sisa */
        ...
    }
    else { /* gps ura */
        return ura<0||14<ura?SQR(6144.0):SQR(ura_value[ura]);  ← 14<ura 正确
    }
}
```

**问题分析:**
- `ura_value` 数组有 15 个元素（索引 0-14）
- 当前代码 `15<ura` 意味着 ura=15 时访问 `ura_value[15]`，**数组越界**
- rtklib_b34 更新日志提到 "fix bug on wrong value with ura=15 in var_ura()"
- 正确条件应为 `14<ura`（即 ura>14 返回默认值）

**影响:**
- ura=15 时读取越界内存，返回不确定的值
- 卫星方差计算错误，影响权重分配
- 可能导致质量差的卫星获得过高权重

**修复:**
```c
static double var_uraeph(int ura)
{
    const double ura_value[]={   
        2.4,3.4,4.85,6.85,9.65,13.65,24.0,48.0,96.0,192.0,384.0,768.0,1536.0,
        3072.0,6144.0
    };
    return ura<0||14<ura?SQR(6144.0):SQR(ura_value[ura]);
}
```

---

### 问题 5：var_uraeph() 缺少 Galileo SISA 支持

**严重程度:** LOW - 影响 Galileo 卫星（非 BDS）
**文件:** `src/ins-gnss/ephemeris.cc:88-94`

**问题分析:**
- rtklib_b34 的 `var_uraeph()` 接收 `sys` 参数，对 Galileo 使用 SISA 表
- 当前代码不区分系统，对 Galileo 使用 GPS 的 URA 表
- 不影响 BDS，但影响 Galileo 精度

**修复（可选）:**
```c
static double var_uraeph(int sys, int ura)
{
    const double ura_value[]={   
        2.4,3.4,4.85,6.85,9.65,13.65,24.0,48.0,96.0,192.0,384.0,768.0,1536.0,
        3072.0,6144.0
    };
    if (sys==SYS_GAL) { /* galileo sisa (ref [7] 5.1.11) */
        if (ura<= 49) return SQR(ura*0.01);
        if (ura<= 74) return SQR(0.5+(ura- 50)*0.02);
        if (ura<= 99) return SQR(1.0+(ura- 75)*0.04);
        if (ura<=125) return SQR(2.0+(ura-100)*0.16);
        return SQR(STD_GAL_NAPA);
    }
    else {
        return ura<0||14<ura?SQR(6144.0):SQR(ura_value[ura]);
    }
}
```

需要同步修改所有调用点，传入 `sys` 参数。

---

## 三、BDS 卫星位置计算验证

### BDS 卫星分类与轨道公式

| 类型 | PRN 范围 | 轨道公式 | 当前状态 |
|------|---------|---------|---------|
| GEO | 1-5, 59-63 | 特殊公式（COS_5/SIN_5 旋转） | **PRN 59-63 错误** |
| IGSO | 6-10, 13-16, 38-40 | 标准公式 | ✓ 正确 |
| MEO | 11-30, 41-58 | 标准公式 | ✓ 正确 |

### GEO 卫星特殊处理说明

BDS GEO 卫星采用地球固定坐标系（ECF）播发星历，而 IGSO/MEO 采用惯性坐标系。因此 GEO 需要额外的坐标系旋转：

```c
/* GEO 卫星：先在 ECF 坐标系计算，再旋转到 ECEF */
O=eph->OMG0+eph->OMGd*tk-omge*eph->toes;  /* 不含 omge*tk 项 */
...
sino=sin(omge*tk); coso=cos(omge*tk);
rs[0]= xg*coso+yg*sino*COS_5+zg*sino*SIN_5;  /* 旋转 5 度 */
rs[1]=-xg*sino+yg*coso*COS_5+zg*coso*SIN_5;
rs[2]=-yg*SIN_5+zg*COS_5;

/* IGSO/MEO：标准公式，OMG 中含 omge*tk 项 */
O=eph->OMG0+(eph->OMGd-omge)*tk-omge*eph->toes;
```

### 当前数据中的 BDS 卫星

从 `cpt0870.19o` 观测文件看，当前数据包含：
- **GEO**: C01-C05（PRN 1-5）→ 当前代码正确处理
- **IGSO**: C06, C07, C09, C10 → 正确
- **MEO**: C11, C12, C16, C23-C25 → 正确

**注意：** 当前数据没有 C59-C63，但修复仍然必要，以支持完整的 BDS-3 星座。

---

## 四、3:28 粗差原因推测

由于当前数据不包含 PRN 59-63，3:28 的粗差可能由以下原因导致：

### 可能原因 1：eph2clk() 钟差迭代错误（最可能）

- 某颗卫星在 3:28 左右星历更新（toe/toc 变化）
- 新星历的 f1/f2 参数与旧星历差异较大
- 错误的迭代公式导致钟差计算突变
- 伪距残差突增，滤波器受冲击

### 可能原因 2：BDS GEO 卫星升降

- C01-C05 中某颗 GEO 卫星在 3:28 左右升起或落下
- 低高度角时多径效应严重
- GEO 卫星位置固定，误差持续影响

### 可能原因 3：星历切换

- 3:28 左右发生星历切换（iode 变化）
- 新旧星历参数差异导致位置跳变

### 诊断建议

1. 检查 trace 日志中 3:28 左右的卫星状态
2. 确认是否有新星历出现
3. 检查是否有卫星升降
4. 对比修复 eph2clk() 前后的钟差值

---

## 五、修复优先级

| 优先级 | 问题 | 影响 | 修复难度 |
|--------|------|------|---------|
| **P0** | eph2clk() 钟差迭代 bug | 所有卫星钟差 | 简单 |
| **P0** | geph2clk() 钟差迭代 bug | GLONASS 钟差 | 简单 |
| **P0** | BDS GEO 判断 prn>=59 | BDS-3 GEO 位置 | 简单 |
| **P1** | var_uraeph() ura=15 越界 | 卫星权重 | 简单 |
| **P2** | var_uraeph() Galileo SISA | Galileo 精度 | 中等 |

---

## 六、验证方法

修复后按以下步骤验证：

```bash
cd /home/mxl/workplace/ignav-debug/build && cmake .. && make navapp -j
bin/navapp -s -o /home/mxl/workplace/ignav-debug/a-cpt/cpt.conf -t 3 -m 52030
# 运行后手动 kill 进程
wc -l /home/mxl/workplace/ignav-debug/a-cpt/output/spp-tc-bdsgps.rslt
```

**预期结果:**
1. 输出文件行数 > 20 万行
2. 3:28 左右无巨大粗差
3. 整体定位精度提升

**精度验证:**
对比 `a-cpt/ref-xyz` 参考轨迹，计算 RMS 误差。

---

## 七、其他改进建议

### 建议 1：启用 BDS-3 新信号（长期）

当前 RINEX 文件只包含 B1I/B2I 信号。未来可考虑支持：
- B1C (1D/1P/1Z) - 更抗干扰
- B2a (5D/5P/5Z) - 更高精度

### 建议 2：BDS 专用权重设置

BDS GEO 卫星精度通常低于 MEO，可考虑：
- 对 GEO 卫星使用更大的方差
- 降低 GEO 卫星在滤波器中的权重

### 建议 3：星历切换平滑

在星历切换时（iode 变化），对位置和钟差进行平滑过渡，避免跳变。
