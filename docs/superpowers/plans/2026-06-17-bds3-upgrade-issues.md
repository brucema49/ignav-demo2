# BDS-3 升级问题分析报告

**日期:** 2026-06-17
**背景:** 项目从 RTKLIB b29 升级到 b34 以支持 BDS-3 信号
**问题现象:** 使用 `.vscode/settings.json` 配置（含北斗系统）时无法正常输出结果，但单 GPS 模式可正常工作
**分析范围:** `docs/superpowers/plans/2026-06-04-b34-upgrade-plan.md`、`skills/*.md` 及相关源码

---

## 一、问题定位总结

通过对 b34 升级计划文档、skill 记录和源码的全面检查，发现 **6 个关键问题**，其中 **2 个为导致北斗失效的根因**（CRITICAL），4 个为影响 BDS-3 完整支持的严重问题。

### 根因分析

RINEX 观测文件 `a-cpt/cpt0870.19o` 中北斗信号定义为：
```
C    8 C1I C7I D1I D7I L1I L7I S1I S7I   SYS / # / OBS TYPES
```
即 BDS 卫星使用 **B1I ("1I")** 和 **B2I ("7I")** 信号。

| 信号 | RINEX 代码 | CODE 定义 | 频率 |
|------|-----------|----------|------|
| B1I  | "1I"      | CODE_L1I = 47 | FREQ1_CMP = 1.561098E9 Hz |
| B2I  | "7I"      | CODE_L7I = 27 | FREQ2_CMP = 1.20714E9 Hz |

**核心矛盾：** `code2freq_BDS()` 将 "1I" 映射到 **FREQ1 (B1C = 1.57542E9 Hz)**，而非 **FREQ1_CMP (B1I = 1.561098E9 Hz)**，频率偏差约 **14.322 MHz**，导致波长计算错误，载波相位处理完全失效。

---

## 二、问题详情

### 问题 1：`code2freq_BDS()` 频率映射错误（根因 #1）

**严重程度:** CRITICAL - 导致北斗完全失效
**文件:** `src/ins-gnss/rtkcmn.cc:4116-4128`

**当前代码:**
```c
static int code2freq_BDS(uint8_t code, double *freq) {
    char *obs=code2obs(code);
    switch (obs[0]) {
        case '1': *freq=FREQ1;     return 0; /* B1C */  ← 错误！
        case '2': *freq=FREQ1_CMP; return 0; /* B1I */  ← 错误！
        case '7': *freq=FREQ2_CMP; return 1; /* B2I/B2b */
        case '5': *freq=FREQ5;     return 2; /* B2a */
        case '6': *freq=FREQ3_CMP; return 3; /* B3 */
        case '8': *freq=FREQ8;     return 4; /* B2ab */
    }
    return -1;
}
```

**问题分析:**
- RINEX 3.x 中 "1I"/"1Q"/"1X" 是 **B1I** 信号（FREQ1_CMP = 1.561098E9 Hz）
- RINEX 3.x 中 "1D"/"1P"/"1Z" 是 **B1C** 信号（FREQ1 = 1.57542E9 Hz）
- 当前代码将所有 '1' 开头的代码都映射到 FREQ1 (B1C)，**B1I 信号频率错误**
- '2' 分支映射到 FREQ1_CMP 是错误的，BDS 在 RINEX 中没有 "2" 开头的代码（'2' 是 GPS L2）

**影响:**
- `sat2freq()` 返回错误频率 → 波长计算错误
- 载波相位观测值处理错误（波长差约 1.7 mm/cycle）
- 多普勒处理错误
- 电离层计算错误（双频 gamma 值错误）
- 滤波器发散或无法输出结果

**调用链:**
```
sat2freq() → code2freq() → code2freq_BDS() → 返回错误频率
```

**验证:**
- `obsfreqs[47] = 1`（CODE_L1I）→ 频率索引 0 → `satwavelen()` 返回 CLIGHT/FREQ1_CMP（正确）
- `code2freq_BDS(47)` → '1' → FREQ1（错误！）
- 说明旧的 `satwavelen()` 映射正确，但新的 `code2freq_BDS()` 映射错误

---

### 问题 2：`prange()` BDS TGD 选择错误（根因 #2）

**严重程度:** CRITICAL - 影响伪距修正
**文件:** `src/ins-gnss/pntpos.cc:112-119`（双频）和 `142-147`（单频）

**当前代码（单频）:**
```c
else if (sys==SYS_CMP) { /* B1I/B1Cp/B1Cd */
    if      (obs->code[0]==CODE_L2I) b1=gettgd(sat,nav,0); /* TGD_B1I */
    else if (obs->code[0]==CODE_L1P) b1=gettgd(sat,nav,2); /* TGD_B1Cp */
    else b1=gettgd(sat,nav,2)+gettgd(sat,nav,4); /* TGD_B1Cp+ISC_B1Cd */
    return P1-b1;
}
```

**当前代码（双频）:**
```c
else if (sys==SYS_CMP) { /* B1-B2 */
    gamma=SQR(((obs->code[0]==CODE_L2I)?FREQ1_CMP:FREQ1)/FREQ2_CMP);
    if      (obs->code[0]==CODE_L2I) b1=gettgd(sat,nav,0); /* TGD_B1I */
    else if (obs->code[0]==CODE_L1P) b1=gettgd(sat,nav,2); /* TGD_B1Cp */
    else b1=gettgd(sat,nav,2)+gettgd(sat,nav,4); /* TGD_B1Cp+ISC_B1Cd */
    b2=gettgd(sat,nav,1); /* TGD_B2I/B2bI (m) */
    return ((P2-gamma*P1)-(b2-gamma*b1))/(1.0-gamma);
}
```

**问题分析:**
- RINEX 文件中 BDS B1I 信号代码是 "1I" → `CODE_L1I = 47`
- 但 `prange()` 检查的是 `CODE_L2I = 40`（RINEX 2.x 风格的 "2I"）
- "C1I" (CODE_L1I) 会落入 `else` 分支，使用 `tgd[2]+tgd[4]`（均为 0）
- 正确行为应使用 `tgd[0]`（TGD_B1I）

**CODE 定义对照:**
| CODE 常量 | 值 | RINEX 代码 | 含义 |
|----------|---|-----------|------|
| CODE_L2I | 40 | "2I" | BDS B1I（RINEX 2.x 风格）|
| CODE_L1I | 47 | "1I" | BDS B1I（RINEX 3.x 风格）|

**影响:**
- 单频模式：TGD 修正为 0（应为 tgd[0]），伪距偏差可达数米
- 双频模式：gamma 值错误（用 FREQ1 而非 FREQ1_CMP），TGD 也错误
- 无电离层组合计算完全错误

---

### 问题 3：`obscodes[]` 表缺少 BDS-3 新代码

**严重程度:** HIGH - 影响 BDS-3 B1C/B2a 信号解析
**文件:** `src/ins-gnss/rtkcmn.cc:269-280`

**当前代码:**
```c
static char *obscodes[]={       /* observation code strings */
    ""  ,"1C","1P","1W","1Y", "1M","1N","1S","1L","1E", /*  0- 9 */
    "1A","1B","1X","1Z","2C", "2D","2S","2L","2X","2P", /* 10-19 */
    "2W","2Y","2M","2N","5I", "5Q","5X","7I","7Q","7X", /* 20-29 */
    "6A","6B","6C","6X","6Z", "6S","6L","8L","8Q","8X", /* 30-39 */
    "2I","2Q","6I","6Q","3I", "3Q","3X","1I","1Q","5A", /* 40-49 */
    "5B","5C","9A","9B","9C", "9X",""  ,""  ,""  ,""    /* 50-59 */
};
```

**问题分析:**
- 表只有 60 个条目（索引 0-59）
- 索引 56-59 为空字符串
- 索引 60-68 完全不存在（表越界）
- `navlib.h` 中定义了 CODE_L1D(56) 到 CODE_L8P(65)，但 `obscodes[]` 未对应填充

**缺失的 BDS-3 代码:**
| 索引 | 应为 | 含义 |
|------|------|------|
| 56 | "1D" | B1Cp |
| 57 | "1P" | B1Cp |
| 58 | "1Z" | B1Cp+B1Cd |
| 59 | "5D" | B2aD |
| 60 | "5P" | B2aP |
| 61 | "5Z" | B2aD+P |
| 62 | "7D" | B2bD |
| 63 | "7P" | B2bP |
| 64 | "7Z" | B2bD+P |
| 65 | "8D" | B2abD |
| 66 | "8P" | B2abP |
| 67 | "8Z" | B2abD+P |

**影响:**
- `obs2code()` 无法解析 BDS-3 B1C/B2a 信号代码
- BDS-3 新信号观测值无法被识别和使用

---

### 问题 4：`obsfreqs[]` 表缺少 BDS-3 新代码

**严重程度:** HIGH - 影响 BDS-3 频率索引映射
**文件:** `src/ins-gnss/rtkcmn.cc:287-296`

**当前代码:**
```c
static unsigned char obsfreqs[]={
    /* 1:L1/E1, 2:L2/B1, 3:L5/E5a/L3, 4:L6/LEX/B3, 5:E5b/B2, 6:E5(a+b), 7:S */
    0, 1, 1, 1, 1,  1, 1, 1, 1, 1, /*  0- 9 */
    1, 1, 1, 1, 2,  2, 2, 2, 2, 2, /* 10-19 */
    2, 2, 2, 2, 3,  3, 3, 5, 5, 5, /* 20-29 */
    4, 4, 4, 4, 4,  4, 4, 6, 6, 6, /* 30-39 */
    2, 2, 4, 4, 3,  3, 3, 1, 1, 3, /* 40-49 */
    3, 3, 7, 7, 7,  7, 0, 0, 0, 0  /* 50-59 */
};
```

**问题分析:**
- 表只有 60 个条目
- 索引 56-59 值为 0（未映射）
- 索引 60-68 完全不存在
- BDS-3 新代码无法获得正确的频率索引

**影响:**
- BDS-3 B1C/B2a 信号无法获得频率索引
- 影响 `testsnr()` 等依赖频率索引的函数

---

### 问题 5：BDS `codepri` 表缺少 D/P/Z 代码

**严重程度:** HIGH - 影响 BDS-3 代码优先级选择
**文件:** `src/ins-gnss/rtkcmn.cc:299-307`

**当前代码:**
```c
static char codepris[7][MAXFREQ][16]={  /* code priority table */
   /* L1/E1      L2/B1        L5/E5a/L3 L6/LEX/B3 E5b/B2    E5(a+b)  S */
    {"CPYWMNSL","PYWCMNDSLX","IQX"     ,""       ,""       ,""      ,""    }, /* GPS */
    {"PC"      ,"PC"        ,"IQX"     ,""       ,""       ,""      ,""    }, /* GLO */
    {"CABXZ"   ,""          ,"IQX"     ,"ABCXZ"  ,"IQX"    ,"IQX"   ,""    }, /* GAL */
    {"CSLXZ"   ,"SLX"       ,"IQX"     ,"SLX"    ,""       ,""      ,""    }, /* QZS */
    {"C"       ,""          ,"IQX"     ,""       ,""       ,""      ,""    }, /* SBS */
    {"IQX"     ,"IQX"       ,"IQX"     ,"IQX"    ,"IQX"    ,""      ,""    }, /* BDS */
    {""        ,""          ,"ABCX"    ,""       ,""       ,""      ,"ABCX"}  /* IRN */
};
```

**问题分析:**
- BDS 行所有频率只有 "IQX"，缺少 "D"、"P"、"Z" 代码
- BDS-3 B1C 信号使用 "1D"/"1P"/"1Z"，无法被优先级表选择
- BDS-3 B2a 信号使用 "5D"/"5P"/"5Z"，无法被优先级表选择
- BDS-3 B2b 信号使用 "7D"/"7P"/"7Z"，无法被优先级表选择

**影响:**
- `code2pri()` 无法为 BDS-3 B1C/B2a/B2b 信号计算优先级
- 多信号场景下无法正确选择 BDS-3 信号

---

### 问题 6：`satwavelen()` 未移除（遗留问题）

**严重程度:** MEDIUM - 潜在冲突
**文件:** `src/ins-gnss/rtkcmn.cc:4022-4054`

**当前代码:**
```c
extern double satwavelen(int sat, int frq, const nav_t *nav)
{
    ...
    else if (sys==SYS_CMP) {
        if      (frq==0) return CLIGHT/FREQ1_CMP; /* B1 */  ← 正确
        else if (frq==1) return CLIGHT/FREQ2_CMP; /* B2 */
        else if (frq==2) return CLIGHT/FREQ3_CMP; /* B3 */
    }
    ...
}
```

**问题分析:**
- b34 升级计划要求移除 `satwavelen()`，用 `sat2freq()` 替代
- 但该函数仍然存在
- 讽刺的是，`satwavelen()` 的 BDS 频率映射是**正确的**（FREQ1_CMP）
- 而新的 `code2freq_BDS()` 映射是**错误的**（FREQ1）
- 如果代码中仍有地方调用 `satwavelen()`，会出现不一致

**影响:**
- 新旧函数并存，可能导致频率计算不一致
- 违反 b34 升级设计规范

---

## 三、问题影响链

```
RINEX 文件 BDS 信号 "1I" (B1I)
         │
         ▼
obs2code("1I") → CODE_L1I = 47
         │
         ├──→ sat2freq(sat, 47, nav)
         │         │
         │         ▼
         │    code2freq_BDS(47)
         │         │
         │         ▼
         │    obs[0]='1' → FREQ1 (B1C = 1.57542E9)  ← 错误！
         │         │                              应为 FREQ1_CMP (B1I = 1.561098E9)
         │         ▼
         │    波长 = CLIGHT/FREQ1 ≈ 0.1903 m  ← 错误！
         │                              应为 CLIGHT/FREQ1_CMP ≈ 0.1920 m
         │         │
         │         ▼
         │    载波相位距离 = phase × 0.1903  ← 错误！
         │                              应为 phase × 0.1920
         │         │
         │         ▼
         │    滤波器发散 / 无结果输出
         │
         └──→ prange(obs)
                   │
                   ▼
              obs->code[0] == CODE_L2I?  ← 否 (CODE_L1I=47 ≠ CODE_L2I=40)
                   │
                   ▼
              obs->code[0] == CODE_L1P?  ← 否
                   │
                   ▼
              b1 = tgd[2]+tgd[4] = 0  ← 错误！应为 tgd[0] (TGD_B1I)
                   │
                   ▼
              伪距修正错误 (少修正数米)
```

---

## 四、修复建议（暂不实施）

### 修复 1：`code2freq_BDS()` 频率映射

**文件:** `src/ins-gnss/rtkcmn.cc:4116-4128`

**方案 A（最小修复，仅支持 B1I）:**
```c
static int code2freq_BDS(uint8_t code, double *freq) {
    char *obs=code2obs(code);
    switch (obs[0]) {
        case '1': *freq=FREQ1_CMP; return 0; /* B1I */
        case '7': *freq=FREQ2_CMP; return 1; /* B2I/B2b */
        case '5': *freq=FREQ5;     return 2; /* B2a */
        case '6': *freq=FREQ3_CMP; return 3; /* B3 */
        case '8': *freq=FREQ8;     return 4; /* B2ab */
    }
    return -1;
}
```

**方案 B（完整支持 B1I + B1C）:**
```c
static int code2freq_BDS(uint8_t code, double *freq) {
    char *obs=code2obs(code);
    switch (obs[0]) {
        case '1':
            if (obs[1]=='I'||obs[1]=='Q'||obs[1]=='X') {
                *freq=FREQ1_CMP; return 0; /* B1I */
            } else {
                *freq=FREQ1;     return 0; /* B1C */
            }
        case '7': *freq=FREQ2_CMP; return 1; /* B2I/B2b */
        case '5': *freq=FREQ5;     return 2; /* B2a */
        case '6': *freq=FREQ3_CMP; return 3; /* B3 */
        case '8': *freq=FREQ8;     return 4; /* B2ab */
    }
    return -1;
}
```

### 修复 2：`prange()` TGD 选择

**文件:** `src/ins-gnss/pntpos.cc:112-119` 和 `142-147`

```c
/* 单频 */
else if (sys==SYS_CMP) { /* B1I/B1Cp/B1Cd */
    if      (obs->code[0]==CODE_L2I||obs->code[0]==CODE_L1I) b1=gettgd(sat,nav,0); /* TGD_B1I */
    else if (obs->code[0]==CODE_L1P) b1=gettgd(sat,nav,2); /* TGD_B1Cp */
    else b1=gettgd(sat,nav,2)+gettgd(sat,nav,4); /* TGD_B1Cp+ISC_B1Cd */
    return P1-b1;
}

/* 双频 */
else if (sys==SYS_CMP) { /* B1-B2 */
    int isB1I = (obs->code[0]==CODE_L2I||obs->code[0]==CODE_L1I);
    gamma=SQR((isB1I?FREQ1_CMP:FREQ1)/FREQ2_CMP);
    if      (isB1I)                 b1=gettgd(sat,nav,0); /* TGD_B1I */
    else if (obs->code[0]==CODE_L1P) b1=gettgd(sat,nav,2); /* TGD_B1Cp */
    else b1=gettgd(sat,nav,2)+gettgd(sat,nav,4); /* TGD_B1Cp+ISC_B1Cd */
    b2=gettgd(sat,nav,1); /* TGD_B2I/B2bI (m) */
    return ((P2-gamma*P1)-(b2-gamma*b1))/(1.0-gamma);
}
```

### 修复 3：补全 `obscodes[]` 表

**文件:** `src/ins-gnss/rtkcmn.cc:269-280`

```c
static char *obscodes[]={       /* observation code strings */
    ""  ,"1C","1P","1W","1Y", "1M","1N","1S","1L","1E", /*  0- 9 */
    "1A","1B","1X","1Z","2C", "2D","2S","2L","2X","2P", /* 10-19 */
    "2W","2Y","2M","2N","5I", "5Q","5X","7I","7Q","7X", /* 20-29 */
    "6A","6B","6C","6X","6Z", "6S","6L","8L","8Q","8X", /* 30-39 */
    "2I","2Q","6I","6Q","3I", "3Q","3X","1I","1Q","5A", /* 40-49 */
    "5B","5C","9A","9B","9C", "9X","1D","1P","1Z","5D", /* 50-59 */
    "5P","5Z","7D","7P","7Z", "8D","8P","8Z"            /* 60-67 */
};
```

### 修复 4：补全 `obsfreqs[]` 表

**文件:** `src/ins-gnss/rtkcmn.cc:287-296`

```c
static unsigned char obsfreqs[]={
    /* 1:L1/E1, 2:L2/B1, 3:L5/E5a/L3, 4:L6/LEX/B3, 5:E5b/B2, 6:E5(a+b), 7:S */
    0, 1, 1, 1, 1,  1, 1, 1, 1, 1, /*  0- 9 */
    1, 1, 1, 1, 2,  2, 2, 2, 2, 2, /* 10-19 */
    2, 2, 2, 2, 3,  3, 3, 5, 5, 5, /* 20-29 */
    4, 4, 4, 4, 4,  4, 4, 6, 6, 6, /* 30-39 */
    2, 2, 4, 4, 3,  3, 3, 1, 1, 3, /* 40-49 */
    3, 3, 7, 7, 7,  7, 1, 1, 1, 3, /* 50-59 */  /* 56-58:B1C→L1, 59:B2a→L5 */
    3, 3, 5, 5, 5,  6, 6, 6        /* 60-67 */  /* 60-61:B2a, 62-64:B2b, 65-67:B2ab */
};
```

### 修复 5：补全 BDS `codepri` 表

**文件:** `src/ins-gnss/rtkcmn.cc:305`

```c
{"IQXDPZ"  ,"IQX"       ,"IQXDPZ"  ,"IQX"    ,"IQXDPZ" ,""      ,""    }, /* BDS */
```

### 修复 6：移除 `satwavelen()`

**文件:** `src/ins-gnss/rtkcmn.cc:4022-4054`

确认无调用后删除该函数，统一使用 `sat2freq()`。

---

## 五、验证方法

修复后按以下步骤验证：

```bash
cd /home/mxl/workplace/ignav-debug/build && cmake .. && make navapp -j
bin/navapp -s -o /home/mxl/workplace/ignav-debug/a-cpt/cpt.conf -t 3 -m 52030
pkill -9 navapp
wc -l /home/mxl/workplace/ignav-debug/a-cpt/spp-tc.rslt
```

**预期结果:** `spp-tc.rslt` 文件应有非零行数输出，包含 BDS 卫星的定位结果。

---

## 六、与升级计划文档的对照

参考 `docs/superpowers/plans/2026-06-04-b34-upgrade-plan.md`：

| 计划任务 | 实施状态 | 问题 |
|---------|---------|------|
| Task 1.1: 更新常量 | ✓ 已完成 | - |
| Task 1.2: 新增 CODE 定义 | ✓ 已完成 | obscodes/obsfreqs 表未同步更新 |
| Task 1.3: 新增 code2freq_BDS | ✓ 已完成 | **频率映射错误** |
| Task 1.4: 新增 code2idx/sat2freq | ✓ 已完成 | 依赖错误的 code2freq_BDS |
| Task 2.x: 迁移调用点 | ✓ 已完成 | - |
| Task 3.x: codepri 更新 | ✗ 未完成 | **BDS codepri 缺少 D/P/Z** |
| Task 4.x: prange TGD | ✓ 已完成 | **CODE_L1I 未处理** |
| Task 5.x: 移除旧代码 | ✗ 未完成 | **satwavelen() 仍存在** |

---

## 七、结论

北斗系统无法正常输出的**根本原因**是 `code2freq_BDS()` 函数将 B1I 信号 ("1I") 的频率错误映射为 FREQ1 (B1C 频率)，导致载波相位波长计算错误，滤波器发散。

**次要原因**是 `prange()` 函数未识别 RINEX 3.x 风格的 B1I 代码 (CODE_L1I)，导致 TGD 修正错误。

修复优先级：
1. **P0（必须）:** 修复 `code2freq_BDS()` 频率映射
2. **P0（必须）:** 修复 `prange()` CODE_L1I 识别
3. **P1（重要）:** 补全 `obscodes[]` 和 `obsfreqs[]` 表
4. **P1（重要）:** 补全 BDS `codepri` 表
5. **P2（建议）:** 移除 `satwavelen()`
