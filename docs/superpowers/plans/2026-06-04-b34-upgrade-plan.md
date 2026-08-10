# RTKLIB b34 升级实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 ignav-debug 项目的 GNSS 部分从 RTKLIB b29 升级到 b34，支持 BDS-3、RINEX 2.x、SNR_UNIT 单位迁移、lam_carr 移除。

**Architecture:** 增量安全推进——先加法后减法：第 1 步新增常量和函数（不破坏旧代码），第 2-4 步逐组迁移调用点，第 5 步删除旧代码和新增 RINEX 2.x 功能。每步编译运行验证。

**Build & Test:**
```bash
cd /home/mxl/workplace/ignav-debug/build && cmake .. && make navapp -j
bin/navapp -s -o /home/mxl/workplace/ignav-debug/a-cpt/cpt.conf -t 3 -m 52030
# 运行一段时间后:
pkill -9 navapp
wc -l /home/mxl/workplace/ignav-debug/a-cpt/spp-tc.rslt
```

**Tech Stack:** C++11, CMake, RTKLIB, INS/GNSS 紧组合

---

## Step 1：常量 + 新函数（纯加法）

### Task 1.1：更新卫星系统常量

**文件:** `include/navlib.h`

- [ ] **修改 PATCH_LEVEL**

`include/navlib.h:76`:
```
#define PATCH_LEVEL "b29"  →  #define PATCH_LEVEL "b34"
```

- [ ] **修改 MAXPRNGAL**

`include/navlib.h:187`:
```
#define MAXPRNGAL   30  →  #define MAXPRNGAL   36
```

- [ ] **修改 MAXPRNQZS 和 MAXPRNQZS_S**

`include/navlib.h:198`:
```
#define MAXPRNQZS   199  →  #define MAXPRNQZS   202
```
`include/navlib.h:200`:
```
#define MAXPRNQZS_S 189  →  #define MAXPRNQZS_S 191
```

- [ ] **修改 MAXPRNCMP**

`include/navlib.h:213`:
```
#define MAXPRNCMP   35  →  #define MAXPRNCMP   63
```

- [ ] **修改 MAXPRNIRN**

`include/navlib.h:224`:
```
#define MAXPRNIRN   7   →  #define MAXPRNIRN   14
```

- [ ] **修改 MAXPRNSBS**

`include/navlib.h:248`:
```
#define MAXPRNSBS   142  →  #define MAXPRNSBS   158
```

- [ ] **修改 MAXCODE**

`include/navlib.h:384`:
```
#define MAXCODE     55  →  #define MAXCODE     68
```

- [ ] **修改 MAXOBS**

`include/navlib.h:256`:
```
#define MAXOBS      64  →  #define MAXOBS      96
```

- [ ] **修改 MAXCOMMENT**

`include/navlib.h:287`:
```
#define MAXCOMMENT  10  →  #define MAXCOMMENT  100
```

- [ ] **修改 MAXRAWLEN**

`include/navlib.h:293`:
```
#define MAXRAWLEN   4096  →  #define MAXRAWLEN   16384
```

- [ ] **修改 MAXDTOE_GAL**

`include/navlib.h:270`:
```
#define MAXDTOE_GAL 10800.0  →  #define MAXDTOE_GAL 14400.0
```

### Task 1.2：新增频率常量和新码类型

**文件:** `include/navlib.h`

- [ ] **在 FREQ6 定义后新增频率常量**

在 `FREQ9` 定义后（约行 113 附近），新增：
```c
#define FREQ1a_GLO  1.600995E9          /* GLONASS G1a frequency (Hz) */
#define FREQ2a_GLO  1.248060E9          /* GLONASS G2a frequency (Hz) */
#define SNR_UNIT    0.001               /* SNR unit (dBHz) */
```

- [ ] **在 CODE_L9X=55 之后新增码类型**

在 `include/navlib.h:383`（`CODE_L9X` 定义）之后，`MAXCODE` 之前，新增：
```c
#define CODE_L1D    56   /* B1D (BDS) */
#define CODE_L5D    57   /* L5D/B2aD (QZS,BDS) */
#define CODE_L5P    58   /* L5P/B2aP (QZS,BDS) */
#define CODE_L5Z    59   /* L5D+P (QZS) */
#define CODE_L6E    60   /* L6E (QZS) */
#define CODE_L7D    61   /* B2bD (BDS) */
#define CODE_L7P    62   /* B2bP (BDS) */
#define CODE_L7Z    63   /* B2bD+P (BDS) */
#define CODE_L8D    64   /* B2abD (BDS) */
#define CODE_L8P    65   /* B2abP (BDS) */
#define CODE_L4A    66   /* G1aL1OCd (GLO) */
#define CODE_L4B    67   /* G1aL1OCd (GLO) */
#define CODE_L4X    68   /* G1al1OCd+p (GLO) */
```

### Task 1.3：结构体扩展

**文件:** `include/navlib.h`

- [ ] **扩展 eph_t.tgd[4] → [6]**

`include/navlib.h:1267`:
```c
// 修改前
double tgd[4];      /* group delay parameters */
                    /* GPS/QZS:tgd[0]=TGD */
                    /* GAL    :tgd[0]=BGD E5a/E1,tgd[1]=BGD E5b/E1 */
                    /* CMP    :tgd[0]=BGD1,tgd[1]=BGD2 */
// 修改后
double tgd[6];      /* group delay parameters */
                    /* GPS/QZS:tgd[0]=TGD */
                    /* GAL:tgd[0]=BGD_E1E5a,tgd[1]=BGD_E1E5b */
                    /* CMP:tgd[0]=TGD_B1I ,tgd[1]=TGD_B2I/B2b,tgd[2]=TGD_B1Cp */
                    /*     tgd[3]=TGD_B2ap,tgd[4]=ISC_B1Cd   ,tgd[5]=ISC_B2ad */
```

- [ ] **扩展 nav_t.utc_* 数组**

`include/navlib.h:1530-1535`:
```c
// 修改前
double utc_gps[4];   →  double utc_gps[8];
double utc_glo[4];   →  double utc_glo[8];
double utc_gal[4];   →  double utc_gal[8];
double utc_qzs[4];   →  double utc_qzs[8];
double utc_cmp[4];   →  double utc_cmp[8];
double utc_irn[4];   →  double utc_irn[9];   // IRNSS 特殊: 9 个元素
```

- [ ] **修改 nav_t.glo_fcn 类型**

`include/navlib.h:1548`:
```c
// 修改前
char glo_fcn[MAXPRNGLO+1];  /* glonass frequency channel number + 8 */
// 修改后
int glo_fcn[32];            /* glonass frequency channel number + 8 */
```

- [ ] **扩展 sta_t**

`include/navlib.h`，在 `sta_t` 的 `double hgt;` 行后（约行 1581），`} sta_t;` 之前，追加：
```c
    int glo_cp_align;       /* GLONASS code-phase alignment (0:no,1:yes) */
    double glo_cp_bias[4];  /* GLONASS code-phase biases {1C,1P,2C,2P} (m) */
```

### Task 1.4：实现 code2freq 函数族

**文件:** `src/ins-gnss/rtkcmn.cc`

- [ ] **在 rtkcmn.cc 末尾添加 code2freq_* 函数**

在 `satwavelen()` 函数之后或文件中合适位置添加以下函数。参考 `rtklib_b34/rtkcmn.c:599-689`：

```c
/* GPS obs code to frequency --------------------------------------------------*/
static int code2freq_GPS(uint8_t code, double *freq)
{
    char *obs=code2obs(code);
    switch (obs[0]) {
        case '1': *freq=FREQ1; return 0; /* L1 */
        case '2': *freq=FREQ2; return 1; /* L2 */
        case '5': *freq=FREQ5; return 2; /* L5 */
    }
    return -1;
}
/* GLONASS obs code to frequency ---------------------------------------------*/
static int code2freq_GLO(uint8_t code, int fcn, double *freq)
{
    char *obs=code2obs(code);
    if (fcn<-7||fcn>6) return -1;
    switch (obs[0]) {
        case '1': *freq=FREQ1_GLO+DFRQ1_GLO*fcn; return 0; /* G1 */
        case '2': *freq=FREQ2_GLO+DFRQ2_GLO*fcn; return 1; /* G2 */
        case '3': *freq=FREQ3_GLO;               return 2; /* G3 */
        case '4': *freq=FREQ1a_GLO;              return 0; /* G1a */
        case '6': *freq=FREQ2a_GLO;              return 1; /* G2a */
    }
    return -1;
}
/* Galileo obs code to frequency ---------------------------------------------*/
static int code2freq_GAL(uint8_t code, double *freq)
{
    char *obs=code2obs(code);
    switch (obs[0]) {
        case '1': *freq=FREQ1; return 0; /* E1 */
        case '7': *freq=FREQ7; return 1; /* E5b */
        case '5': *freq=FREQ5; return 2; /* E5a */
        case '6': *freq=FREQ6; return 3; /* E6 */
        case '8': *freq=FREQ8; return 4; /* E5ab */
    }
    return -1;
}
/* QZSS obs code to frequency ------------------------------------------------*/
static int code2freq_QZS(uint8_t code, double *freq)
{
    char *obs=code2obs(code);
    switch (obs[0]) {
        case '1': *freq=FREQ1; return 0; /* L1 */
        case '2': *freq=FREQ2; return 1; /* L2 */
        case '5': *freq=FREQ5; return 2; /* L5 */
        case '6': *freq=FREQ6; return 3; /* L6 */
    }
    return -1;
}
/* SBAS obs code to frequency ------------------------------------------------*/
static int code2freq_SBS(uint8_t code, double *freq)
{
    char *obs=code2obs(code);
    switch (obs[0]) {
        case '1': *freq=FREQ1; return 0; /* L1 */
        case '5': *freq=FREQ5; return 1; /* L5 */
    }
    return -1;
}
/* BDS obs code to frequency -------------------------------------------------*/
static int code2freq_BDS(uint8_t code, double *freq)
{
    char *obs=code2obs(code);
    switch (obs[0]) {
        case '1': *freq=FREQ1;     return 0; /* B1C */
        case '2': *freq=FREQ1_CMP; return 0; /* B1I */
        case '7': *freq=FREQ2_CMP; return 1; /* B2I/B2b */
        case '5': *freq=FREQ5;     return 2; /* B2a */
        case '6': *freq=FREQ3_CMP; return 3; /* B3 */
        case '8': *freq=FREQ8;     return 4; /* B2ab */
    }
    return -1;
}
/* NavIC obs code to frequency -----------------------------------------------*/
static int code2freq_IRN(uint8_t code, double *freq)
{
    char *obs=code2obs(code);
    switch (obs[0]) {
        case '5': *freq=FREQ5; return 0; /* L5 */
        case '9': *freq=FREQ9; return 1; /* S */
    }
    return -1;
}
```

### Task 1.5：实现 code2idx / code2freq / sat2freq

**文件:** `src/ins-gnss/rtkcmn.cc`

- [ ] **在 code2freq_* 函数之后添加公共 API**

参考 `rtklib_b34/rtkcmn.c:705-769`：

```c
/* system and obs code to frequency index ------------------------------------*/
extern int code2idx(int sys, uint8_t code)
{
    double freq;
    switch (sys) {
        case SYS_GPS: return code2freq_GPS(code,&freq);
        case SYS_GLO: return code2freq_GLO(code,0,&freq);
        case SYS_GAL: return code2freq_GAL(code,&freq);
        case SYS_QZS: return code2freq_QZS(code,&freq);
        case SYS_SBS: return code2freq_SBS(code,&freq);
        case SYS_CMP: return code2freq_BDS(code,&freq);
        case SYS_IRN: return code2freq_IRN(code,&freq);
    }
    return -1;
}
/* system and obs code to frequency ------------------------------------------*/
extern double code2freq(int sys, uint8_t code, int fcn)
{
    double freq=0.0;
    switch (sys) {
        case SYS_GPS: (void)code2freq_GPS(code,&freq); break;
        case SYS_GLO: (void)code2freq_GLO(code,fcn,&freq); break;
        case SYS_GAL: (void)code2freq_GAL(code,&freq); break;
        case SYS_QZS: (void)code2freq_QZS(code,&freq); break;
        case SYS_SBS: (void)code2freq_SBS(code,&freq); break;
        case SYS_CMP: (void)code2freq_BDS(code,&freq); break;
        case SYS_IRN: (void)code2freq_IRN(code,&freq); break;
    }
    return freq;
}
/* satellite and obs code to frequency ---------------------------------------*/
extern double sat2freq(int sat, uint8_t code, const nav_t *nav)
{
    int i,fcn=0,sys,prn;
    sys=satsys(sat,&prn);
    if (sys==SYS_GLO) {
        if (!nav) return 0.0;
        for (i=0;i<nav->ng;i++) {
            if (nav->geph[i].sat==sat) break;
        }
        if (i<nav->ng) {
            fcn=nav->geph[i].frq;
        }
        else if (nav->glo_fcn[prn-1]>0) {
            fcn=nav->glo_fcn[prn-1]-8;
        }
        else return 0.0;
    }
    return code2freq(sys,code,fcn);
}
```

### Task 1.6：更新 obs2code/code2obs 签名 + 声明

**文件:** `include/navlib.h`

- [ ] **更新 obs2code/code2obs 声明**

`include/navlib.h:2347-2348`:
```c
// 修改前
EXPORT unsigned char obs2code(const char *obs, int *freq);
EXPORT char *code2obs(unsigned char code, int *freq);
// 修改后
EXPORT uint8_t obs2code(const char *obs);
EXPORT char *code2obs(uint8_t code);
```

- [ ] **新增函数声明**

在 `include/navlib.h` 中 `code2obs` 声明之后添加：
```c
EXPORT double code2freq(int sys, uint8_t code, int fcn);
EXPORT double sat2freq(int sat, uint8_t code, const nav_t *nav);
EXPORT int  code2idx(int sys, uint8_t code);
```

- [ ] **更新 obs2code/code2obs 实现签名**

`src/ins-gnss/rtkcmn.cc:607-678` — 将 `obs2code` 和 `code2obs` 函数签名更新为 `uint8_t` 类型，去掉 `freq` 参数。

当前签名:
```c
extern unsigned char obs2code(const char *obs, int *freq)
```

改为:
```c
extern uint8_t obs2code(const char *obs)
```

当前签名:
```c
extern char *code2obs(unsigned char code, int *freq)
```

改为:
```c
extern char *code2obs(uint8_t code)
```

注意：`code2obs()` 返回 `char*`，`obs2code()` 返回 `uint8_t`。需要查找所有调用 `code2obs(..., &freq)` 和 `obs2code(..., &freq)` 的地方，移除第二个参数。

编译时会报错，通过编译错误定位所有调用点。

**所有调用点列表（搜索 `obs2code` 和 `code2obs`）:**
- `src/ins-gnss/rtkcmn.cc` — 内部调用
- `src/ins-gnss/rinex.cc` — 可能引用
- `src/ins-gnss/rcv/rinex-rt.cc` — 可能引用
- 其他接收机驱动文件

### Task 1.7：构建并测试

- [ ] **编译**

```bash
cd /home/mxl/workplace/ignav-debug/build && cmake .. && make navapp -j 2>&1
```
预期: 编译通过（可能因 obs2code/code2obs 签名变更有编译错误，逐一修复）。

- [ ] **运行测试**

```bash
cd /home/mxl/workplace/ignav-debug
bin/navapp -s -o a-cpt/cpt.conf -t 3 -m 52030
```
等待一段时间后:
```bash
pkill -9 navapp
wc -l a-cpt/spp-tc.rslt
```
预期: 输出有约 23 万行。

- [ ] **提交**

```bash
git add -A
git commit -m "step1: update constants, code types, code2freq/sat2freq/code2idx"
```

---

## Step 2：P0 核心函数迁移

### Task 2.1：satexclude() 增加 var 参数

**文件:** `include/navlib.h`, `src/ins-gnss/rtkcmn.cc`, `src/ins-gnss/pntpos.cc`, `src/ins-gnss/rtkpos.cc`, `src/ins-gnss/ppp.cc`, `src/ins-gnss/ins-doppler.cc`

- [ ] **添加 MAX_VAR_EPH 宏**

`include/navlib.h` 中合适位置（如 `MAXDTOE` 附近）添加：
```c
#define MAX_VAR_EPH SQR(300.0)          /* max variance of ephemeris (m^2) */
```

- [ ] **更新 satexclude 声明**

`include/navlib.h:2349`:
```c
// 修改前
EXPORT int  satexclude(int sat, int svh, const prcopt_t *opt);
// 修改后
EXPORT int  satexclude(int sat, double var, int svh, const prcopt_t *opt);
```

- [ ] **更新 satexclude 实现**

`src/ins-gnss/rtkcmn.cc:556-570`:
```c
// 修改前
extern int satexclude(int sat, int svh, const prcopt_t *opt)
{
    int sys=satsys(sat,NULL);
    
    if (svh<0) return 1; /* ephemeris unavailable */
    if (opt) {
        if (opt->exsats[sat-1]==1) return 1; /* excluded satellite */
        if (opt->exsats[sat-1]==2) return 0; /* included satellite */
        if (!(sys&opt->navsys)) return 1; /* unselected sat sys */
    }
    if (sys==SYS_QZS) svh&=0xFE; /* mask QZSS LEX health */
    if (svh) {
        trace(3,"unhealthy satellite: sat=%3d svh=%02X\n",sat,svh);
        return 1;
    }
    return 0;
}
// 修改后
extern int satexclude(int sat, double var, int svh, const prcopt_t *opt)
{
    int sys=satsys(sat,NULL);
    
    if (svh<0) return 1; /* ephemeris unavailable */
    if (opt) {
        if (opt->exsats[sat-1]==1) return 1; /* excluded satellite */
        if (opt->exsats[sat-1]==2) return 0; /* included satellite */
        if (!(sys&opt->navsys)) return 1; /* unselected sat sys */
    }
    if (sys==SYS_QZS) svh&=0xFE; /* mask QZSS LEX health */
    if (svh) {
        trace(3,"unhealthy satellite: sat=%3d svh=%02X\n",sat,svh);
        return 1;
    }
    if (var>MAX_VAR_EPH) {
        trace(3,"invalid ura satellite: sat=%3d ura=%.2f\n",sat,sqrt(var));
        return 1;
    }
    return 0;
}
```

- [ ] **更新 pntpos.cc 调用点**

`src/ins-gnss/pntpos.cc:303`:
```c
// 修改前
if (satexclude(obs[i].sat,svh[i],opt)) continue;
// 修改后
if (satexclude(obs[i].sat,vare[i],svh[i],opt)) continue;
```

- [ ] **更新 rtkpos.cc 调用点**

`src/ins-gnss/rtkpos.cc:1185`:
```c
// 修改前
if (satexclude(obs[i].sat,svh[i],opt)) continue;
// 修改后
if (satexclude(obs[i].sat,var[i],svh[i],opt)) continue;
```

- [ ] **更新 ppp.cc 调用点**

查找 `ppp.cc` 中 `satexclude` 调用处（约行 1146）：
```c
// 修改前
if (satexclude(obs[i].sat,svh[i],opt)) continue;
// 修改后
if (satexclude(obs[i].sat,var_rs[i],svh[i],opt)) continue;
```

- [ ] **更新 ins-doppler.cc 调用点**

查找 `ins-doppler.cc` 中 `satexclude` 调用处（约行 180），增加 var 参数。

### Task 2.2：gettgd() 提升 + prange() BDS-3 TGD

**文件:** `src/ins-gnss/pntpos.cc`, `src/ins-gnss/rtkcmn.cc`, `src/ins-gnss/ephemeris.cc`

- [ ] **从 pntpos.cc 删除旧 gettgd**

删除 `src/ins-gnss/pntpos.cc:76-85` 的旧 `static double gettgd(int sat, const nav_t *nav)`。

- [ ] **在 rtkcmn.cc 中实现新 gettgd**

在 `src/ins-gnss/rtkcmn.cc` 中添加全局 `gettgd`（参考 `rtklib_b34/pntpos.c:58-84`）:
```c
/* group delay correction ----------------------------------------------------*/
static double gettgd(int sat, const nav_t *nav, int type)
{
    int sys=satsys(sat,NULL);
    
    if (sys==SYS_GLO) {
        return nav->geph[sat-1].taun*CLIGHT; /* -dtaun (m) */
    }
    if (type<0||6<type) return 0.0;
    return nav->eph[sat-1].tgd[type]*CLIGHT; /* TGD (m) */
}
```

注意：`nav->geph[sat-1]` 需要正确索引。参考 b34 实现：
```c
static double gettgd(int sat, const nav_t *nav, int type)
{
    int i,sys=satsys(sat,NULL);
    
    if (sys==SYS_GLO) {
        for (i=0;i<nav->ng;i++) {
            if (nav->geph[i].sat!=sat) continue;
            return nav->geph[i].taun*CLIGHT; /* -dtaun (m) */
        }
        return 0.0;
    }
    if (type<0||6<type) return 0.0;
    return nav->eph[sat-1].tgd[type]*CLIGHT; /* TGD (m) */
}
```

- [ ] **实现 getseleph()**

在 `src/ins-gnss/ephemeris.cc` 末尾添加（参考 `rtklib_b34/ephemeris.c:839-851`）：
```c
extern int getseleph(int sys)
{
    switch (sys) {
        case SYS_GPS: return eph_sel[0];
        case SYS_GLO: return eph_sel[1];
        case SYS_GAL: return eph_sel[2];
        case SYS_QZS: return eph_sel[3];
        case SYS_CMP: return eph_sel[4];
        case SYS_IRN: return eph_sel[5];
        case SYS_SBS: return eph_sel[6];
    }
    return 0;
}
```

注：需检查 `eph_sel` 是否已在 `navlib.h` 中声明或 ephemeris.cc 中定义。

- [ ] **更新 prange() BDS-3 TGD 分码**

参考 `rtklib_b34/pntpos.c:87-165` 重写 `pntpos.cc` 中 `prange()` 函数。核心修改在 prange() 内的 TGD 处理：
```c
// 双频 IFLC 时的 BDS-3 TGD 处理
if (sys==SYS_CMP) {
    gamma=SQR(((obs->code[0]==CODE_L2I)?FREQ1_CMP:FREQ1)/FREQ2_CMP);
    if      (obs->code[0]==CODE_L2I) b1=gettgd(sat,nav,0); /* TGD_B1I */
    else if (obs->code[0]==CODE_L1P) b1=gettgd(sat,nav,2); /* TGD_B1Cp */
    else b1=gettgd(sat,nav,2)+gettgd(sat,nav,4); /* TGD_B1Cp+ISC_B1Cd */
    b2=gettgd(sat,nav,1);
    return ((P2-gamma*P1)-(b2-gamma*b1))/(1.0-gamma);
}
// GAL BGD 选择
if (sys==SYS_GAL) {
    if (getseleph(SYS_GAL)) b1=gettgd(sat,nav,0); /* BGD_E1E5a (F/NAV) */
    else                    b1=gettgd(sat,nav,1); /* BGD_E1E5b (I/NAV) */
}
```

### Task 2.3：ddres() 电离层缩放 lam_carr → sat2freq

**文件:** `src/ins-gnss/rtkpos.cc`

- [ ] **修改 ddres() 电离层缩放**

`src/ins-gnss/rtkpos.cc:1565`:
```c
// 修改前
fi=lami/lam_carr[0]; fj=lamj/lam_carr[0];
// 修改后
fi=FREQ1/sat2freq(sat[i],obs[iu[i]].code[ff],nav);
fj=FREQ1/sat2freq(sat[j],obs[iu[j]].code[ff],nav);
```

### Task 2.4：构建并测试

- [ ] **编译并修复所有错误**

```bash
cd /home/mxl/workplace/ignav-debug/build && cmake .. && make navapp -j 2>&1
```
预期: 需要修复 gettgd 从 pntpos.cc 移除、新定义在 rtkcmn.cc、所有调用点更新等编译错误。

- [ ] **运行测试**

```bash
cd /home/mxl/workplace/ignav-debug
bin/navapp -s -o a-cpt/cpt.conf -t 3 -m 52030
# 等待后
pkill -9 navapp
wc -l a-cpt/spp-tc.rslt
```
预期: 输出行数约 23 万行（定位结果可能略有变化，但行数正常）。

- [ ] **提交**

```bash
git add -A
git commit -m "step2: satexclude(var), gettgd(type), prange BDS-3, ddres sat2freq"
```

---

## Step 3：SNR 单位迁移

### Task 3.1：navlib.h SNR 类型更新

**文件:** `include/navlib.h`

- [ ] **更新 obsd_t.SNR 类型**

`include/navlib.h:770`:
```c
// 修改前
unsigned char SNR [NFREQ+NEXOBS]; /* signal strength (0.25 dBHz) */
// 修改后
uint16_t SNR[NFREQ+NEXOBS]; /* signal strength (0.001 dBHz) */
```

- [ ] **更新 ssat_t.snr 类型**

`include/navlib.h:1928`:
```c
// 修改前
unsigned char snr [NFREQ]; /* signal strength (0.25 dBHz) */
// 修改后
uint16_t snr[NFREQ]; /* signal strength (*SNR_UNIT dBHz) */
```

- [ ] **更新 lexmsg_t.snr 类型**（2 处）

`include/navlib.h:1455` 和 `include/navlib.h:1673`:
```c
// 修改前
unsigned char snr;  /* signal C/N0 (0.25 dBHz) */
// 修改后
uint16_t snr;       /* signal strength (*SNR_UNIT dBHz) */
```

### Task 3.2：更新 solution.cc

**文件:** `src/ins-gnss/solution.cc`

- [ ] **更新 SNR 写入**

`solution.cc:1380`:
```c
// 修改前
stat->snr  =(unsigned char)(snr*4.0+0.5);
// 修改后
stat->snr  =(uint16_t)(snr/SNR_UNIT+0.5);
```

- [ ] **更新 SNR 读取（3 处）**

`solution.cc:1884,1909,1934`:
```c
// 修改前
snr=ssat[sats[k]-1].snr[0]*0.25;
// 修改后
snr=ssat[sats[k]-1].snr[0]*SNR_UNIT;
```

### Task 3.3：更新 rinex-rt.cc

**文件:** `src/ins-gnss/rcv/rinex-rt.cc`

- [ ] **更新 SNR 写入**

`rinex-rt.cc:298`:
```c
// 修改前
case 3: obs->SNR[p[i]]=(unsigned char)(val[i]*4.0+0.5);    break;
// 修改后
case 3: obs->SNR[p[i]]=(uint16_t)(val[i]/SNR_UNIT+0.5);    break;
```

- [ ] **同步更新 rinex.cc 类似代码**

在 `src/ins-gnss/rinex.cc` 中搜索 `val[i]*4.0+0.5` 和 `snr*4.0+0.5` 模式，全部替换为 `/SNR_UNIT+0.5`。

### Task 3.4：更新接收机驱动文件

- [ ] **更新 novatel.cc（4 处）**

`src/ins-gnss/rcv/novatel.cc:369,457,1126,1193`:
```c
// 修改前
(unsigned char)(snr*4.0+0.5)
// 修改后
(uint16_t)(snr/SNR_UNIT+0.5)
```

- [ ] **更新 rtcm3.cc**

`src/ins-gnss/rtcm3.cc:1949`:
```c
// 修改前
(unsigned char)(cnr[j]*4.0)
// 修改后
(uint16_t)(cnr[j]/SNR_UNIT+0.5)
```

- [ ] **更新 septentrio.cc**

`src/ins-gnss/rcv/septentrio.cc` 中查找 `SNR_DBHZ` 相关转换代码（约行 292,294,427,429），适配 SNR_UNIT。

### Task 3.5：更新 ppp.cc

**文件:** `src/ins-gnss/ppp.cc`

- [ ] **更新 SNR 读取**

`ppp.cc:503`:
```c
// 修改前
if (testsnr(0,0,azel[1],obs->SNR[i]*0.25,&opt->snrmask)) continue;
// 修改后
if (testsnr(0,0,azel[1],obs->SNR[i]*SNR_UNIT,&opt->snrmask)) continue;
```

### Task 3.6：构建并测试

- [ ] **编译**

```bash
cd /home/mxl/workplace/ignav-debug/build && cmake .. && make navapp -j 2>&1
```

- [ ] **运行测试**

```bash
cd /home/mxl/workplace/ignav-debug
bin/navapp -s -o a-cpt/cpt.conf -t 3 -m 52030
# 等待后
pkill -9 navapp
wc -l a-cpt/spp-tc.rslt
```
预期: 输出行数约 23 万行。

- [ ] **提交**

```bash
git add -A
git commit -m "step3: SNR_UNIT migration (unsigned char->uint16_t)"
```

---

## Step 4：RTK/SPP 剩余迁移 + nav->lam 移除

### Task 4.1：rtkpos.cc — zdres + GF 合并

**文件:** `src/ins-gnss/rtkpos.cc`

- [ ] **zdres_sat() 改用 sat2freq**

`rtkpos.cc:1112-1127` — `zdres_sat()` 函数中 `nav->lam` → `sat2freq()`:
```c
// 修改前
const double *lam=nav->lam[obs->sat-1];
...
f1=CLIGHT/lam[0];
f2=CLIGHT/lam[1];
// 修改后
f1=sat2freq(obs->sat,obs->code[0],nav);
f2=sat2freq(obs->sat,obs->code[1],nav);
```

- [ ] **合并 GF 周跳检测函数**

删除 `detslp_gf_L1L2()`（行 843）和 `detslp_gf_L1L5()`（行 862），合并为通用 `detslp_gf()`（参考 `rtklib_b34/rtkpos.c`）：
```c
static void detslp_gf(rtk_t *rtk, const obsd_t *obs, int i, int j,
                       const nav_t *nav)
{
    double gf1,gf2;
    int ti,tj,sat;

    // GF 组合: L1-L2 或 L1-L5
    gf1=gfobs_L1L2(obs,i,j);
    gf2=gfobs_L1L5(obs,i,j);

    // ... 根据可用频率选择检测逻辑
}
```

### Task 4.2：ppp.cc nav->lam → sat2freq

**文件:** `src/ins-gnss/ppp.cc`

- [ ] **迁移 6 处 nav->lam 引用**

`ppp.cc:473,482,496,755,834,1137` — 参考以下模式逐个替换：

位置 1（行 473 — GF 值）:
```c
// 修改前
const double *lam=nav->lam[obs->sat-1];
...
return lam[0]*obs->L[0]-lam[i]*obs->L[i];
// 修改后
freq1=sat2freq(obs->sat,obs->code[0],nav);
freq2=sat2freq(obs->sat,obs->code[i],nav);
return CLIGHT*(obs->L[0]/freq1-obs->L[i]/freq2);
```

位置 2（行 482 — LC 值）:
```c
// 修改后
return SQR(CLIGHT)*(obs->L[0]/freq1-obs->L[1]/freq2)/
       (CLIGHT/freq1-CLIGHT/freq2)-
       (CLIGHT/freq2*obs->P[0]+CLIGHT/freq1*obs->P[1])/
       (CLIGHT/freq1+CLIGHT/freq2);
```

位置 3（行 496 — 无电离层组合）:
```c
// 修改后
freq[i]=sat2freq(obs->sat,obs->code[i],nav);
L[i]=obs->L[i]*CLIGHT/freq[i]-dants[i]-dantr[i]-phw*CLIGHT/freq[i];
```

位置 4-6（行 755, 834, 1137）— 类似替换。

### Task 4.3：lam_carr 残留迁移

**文件:** `src/ins-gnss/ar.cc`, `src/ins-gnss/ppp_ar.cc`, `src/ins-gnss/rtcm3.cc`, `src/ins-gnss/rcvraw.cc`, `src/ins-gnss/rcv/crescent.cc`

- [ ] **迁移 ar.cc（8 处）**

`ar.cc:177-299` 中所有 `lam_carr[0]`、`lam_carr[1]` 替换为 `CLIGHT/sat2freq(...)`。需要获取对应卫星的 code。

- [ ] **迁移 ppp_ar.cc（2 处）**

`ppp_ar.cc:306,358`:
```c
// 修改前
lam1=lam_carr[0]; lam2=lam_carr[1];
// 修改后
lam1=CLIGHT/sat2freq(sat,CODE_L1C,nav);  // 需按实际 code 调整
lam2=CLIGHT/sat2freq(sat,CODE_L2C,nav);
```

- [ ] **迁移 rtcm3.cc（4 处）**

`rtcm3.cc:292-362`:
```c
// 修改前
ppr1*0.0005/lam_carr[0]
pr1/lam_carr[0]+cp1
// 修改后
ppr1*0.0005*sat2freq(sat,CODE_L1C,nav)/CLIGHT
pr1*sat2freq(sat,CODE_L1C,nav)/CLIGHT+cp1
```

- [ ] **迁移 rcvraw.cc（1 处）**

`rcvraw.cc:925`:
```c
// 修改前
raw->nav.lam[i][j]=sys==SYS_GLO?lam_glo[j]:lam_carr[j];
// 修改后
// 删除此行 — lam 表分配不再需要
```

- [ ] **迁移 crescent.cc（8 处）**

`src/ins-gnss/rcv/crescent.cc` 中所有 `lam_carr[0]`、`lam_carr[1]` 替换。

### Task 4.4：构建并测试

- [ ] **编译**

```bash
cd /home/mxl/workplace/ignav-debug/build && cmake .. && make navapp -j 2>&1
```
预期: 可能有 nav->lam 相关编译错误，逐个修复。

- [ ] **运行测试**

```bash
cd /home/mxl/workplace/ignav-debug
bin/navapp -s -o a-cpt/cpt.conf -t 3 -m 52030
# 等待后
pkill -9 navapp
wc -l a-cpt/spp-tc.rslt
```

- [ ] **提交**

```bash
git add -A
git commit -m "step4: rtkpos/ppp sat2freq migration, lam_carr remaining refs"
```

---

## Step 5：清理 + RINEX 2.x

### Task 5.1：删除废弃代码

**文件:** `include/navlib.h`, `src/ins-gnss/rtkcmn.cc`

- [ ] **删除 lam_carr[] 定义**

`src/ins-gnss/rtkcmn.cc:183-186` — 删除 `const double lam_carr[MAXFREQ]` 全局变量。
注意：确保所有引用点在 Step 4 中已迁移完毕，否则编译会报错。编译错误可以帮助定位残留。

- [ ] **删除 satwavelen() 函数**

`src/ins-gnss/rtkcmn.cc:4044` 附近 — 删除 `satwavelen()` 函数。

- [ ] **从 nav_t 删除字段**

`include/navlib.h`:
```c
// 删除行 1542 — int leaps;
// 删除行 1543 — double lam[MAXSAT][NFREQ+NEXOBS*2];
// 删除行 1547 — double glo_cpbias[4];
```

- [ ] **删除 nav->lam 赋值代码**

`src/ins-gnss/rtkcmn.cc:3225,3234`:
```c
// 删除
nav->lam[i][j]=satwavelen(i+1,j,nav);
nav->lam[i][ps->pos[j]+NEXOBS*rcv]=satwavelen(i+1,ps->frq[j]-1,nav);
```

### Task 5.2：RINEX 2.x 实时流支持

**文件:** `src/ins-gnss/rcv/rinex-rt.cc`

- [ ] **新增 convcode() 函数**

在 rinex-rt.cc 中增加 `static void convcode(double ver, int sys, const char *str, char *type)`，参考 `src/ins-gnss/rinex.cc:201-284` 或 `rtklib_b34/rinex.c:263-346`。

- [ ] **修改 decode_obsh() 支持 2.x 头部**

增加 `double ver` 参数。当 `ver<=2.99` 时，处理 `# / TYPES OF OBSERVATIONS` 格式的头部类型行，使用 `convcode()` 做系统转换。

- [ ] **修改 decode_obsepoch() 支持 2.x 历元**

增加 `double ver` 参数。ver<=2.99 时从行首位置读卫星数，卫星 ID 在历元行中，支持多行卫星列表。

- [ ] **修改 decode_obsdata() 支持 2.x 数据行**

ver<=2.99 时卫星号来自历元行中的卫星列表，data 行无 `satid` 前缀。支持 80 列换行逻辑。

- [ ] **修改 input_rinex() 增加版本检测**

增加 RINEX 版本检测逻辑，根据版本分发到不同的解析路径。

### Task 5.3：构建并测试

- [ ] **编译**

```bash
cd /home/mxl/workplace/ignav-debug/build && cmake .. && make navapp -j 2>&1
```

- [ ] **运行测试**

```bash
cd /home/mxl/workplace/ignav-debug
bin/navapp -s -o a-cpt/cpt.conf -t 3 -m 52030
# 等待后
pkill -9 navapp
wc -l a-cpt/spp-tc.rslt
```

- [ ] **提交**

```bash
git add -A
git commit -m "step5: remove lam_carr/satwavelen/nav->lam, RINEX 2.x support"
```

---

## 参考

- 设计文档: `docs/superpowers/specs/2026-06-04-b34-upgrade-design.md`
- SKILL 文件: `.trae/skills/b34-skill/SKILL.md`
- 现状分析: `skills/modify.md`
- b34 参考: `rtklib_b34/rtkcmn.c`, `rtklib_b34/rtklib.h`, `rtklib_b34/pntpos.c`, `rtklib_b34/rtkpos.c`
