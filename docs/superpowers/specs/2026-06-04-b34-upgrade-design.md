# RTKLIB b34 升级实施设计

## 目标

将 ignav-debug 项目的 GNSS 部分从 RTKLIB b29 升级到 b34，涵盖 BDS-3 卫星系统支持、RINEX 2.x 解码、SPP/RTK 核心算法适配、SNR 单位迁移及 lam_carr 移除。

## 约束

1. **每步可编译运行** — 每步修改后执行 `cd build && cmake .. && make navapp -j` 必须编译通过
2. **生成 20 万+ 行输出** — 执行 `bin/navapp -s -o a-cpt/cpt.conf -t 3 -m 52030` 后 `a-cpt/spp-tc.rslt` 行数应为 20 万+
3. **终止进程** — 运行后 `pkill -9 navapp`
4. **步骤合并** — 每步内的变更可合并为单个 commit

## 核心策略：先加法后减法

所有变更按"先新增不破坏现有代码的常量和函数，再逐组迁移调用点，最后移除旧代码"的原则分步推进。

## 构建与测试流程

```bash
# 构建
cd build && cmake .. && make navapp -j

# 测试
bin/navapp -s -o a-cpt/cpt.conf -t 3 -m 52030

# 等待一段时间后终止
pkill -9 navapp

# 验证输出行数
wc -l a-cpt/spp-tc.rslt   # 应为约 230000+
```

### 输入文件
- `a-cpt/cpt0870.19o` — RINEX 观测文件
- `a-cpt/brdm0870.19p` — 广播星历
- `a-cpt/cpt_euroc.csv` — IMU 数据
- `a-cpt/cpt0870_base.19o` — 基站观测数据

### 配置关键参数
- 定位模式: `ins-tightly-coupled`
- 卫星系统: GPS-only (pos1-navsys=1)
- 输出格式: xyz
- 输出路径: `a-cpt/spp-tc.rslt`

## 分步实施计划

### Step 1：常量 + 新函数（纯加法）

**涉及文件**: `include/navlib.h`, `src/ins-gnss/rtkcmn.cc`

**修改清单**:

1. **卫星系统常量更新**（navlib.h）
   - MAXPRNGAL: 30 → 36
   - MAXPRNQZS: 199 → 202
   - MAXPRNQZS_S: 189 → 191
   - MAXPRNCMP: 35 → 63
   - MAXPRNIRN: 7 → 14
   - MAXPRNSBS: 142 → 158
   - MAXCODE: 55 → 68
   - MAXOBS: 64 → 96
   - MAXCOMMENT: 10 → 100
   - MAXRAWLEN: 4096 → 16384
   - MAXDTOE_GAL: 10800.0 → 14400.0

2. **新增频率常量**（navlib.h）
   - FREQ1a_GLO = 1.600995E9
   - FREQ2a_GLO = 1.248060E9
   - SNR_UNIT = 0.001

3. **新增码类型**（navlib.h, CODE_L1D 56 ~ CODE_L4X 68）
   - CODE_L1D(56) ~ CODE_L4X(68)，MAXCODE 从 55 改为 68

4. **结构体扩展**（navlib.h）
   - eph_t.tgd: double[4] → double[6]
   - nav_t.utc_gps/glo/gal/qzs/cmp: [4] → [8]
   - nav_t.utc_irn: [4] → [9]
   - nav_t.glo_fcn: char[MAXPRNGLO+1] → int[32]
   - sta_t: 追加 glo_cp_align(int) + glo_cp_bias(double[4])
   - obsd_t.SNR 类型和 ssat_t.snr 类型暂不变（Step 3 处理）

5. **新增 code2freq 函数族**（rtkcmn.cc + navlib.h 声明）
   - code2freq_GPS/GLO/GAL/QZS/SBS/BDS/IRN（static）
   - code2idx() — 根据系统和码类型返回频率索引
   - code2freq() — 根据系统和码类型返回载波频率
   - sat2freq() — 封装 code2freq + GLONASS FCN 查询

6. **obs2code/code2obs 签名更新**（navlib.h）
   - 更新为 uint8_t 参数类型（b34 兼容）

**影响评估**: 纯新增和扩展，不影响任何现有调用点。编译通过后运行结果应保持不变。

---

### Step 2：P0 核心函数迁移

**涉及文件**: `rtkcmn.cc`, `pntpos.cc`, `rtkpos.cc`, `ppp.cc`, `ephemeris.cc`, `ins-doppler.cc`, `include/navlib.h`

**修改清单**:

1. **satexclude() 增加 var 参数**
   - 签名: `satexclude(int sat, int svh, const prcopt_t *opt)` → `satexclude(int sat, double var, int svh, const prcopt_t *opt)`
   - 新增 `MAX_VAR_EPH = SQR(300.0)` 方差阈值
   - 新增 GLONASS 健康检查逻辑 `(svh&9)!=0 || (svh&6)==4`
   - 所有调用点更新:
     - pntpos.cc:303 — 传入 `vare[i]`
     - rtkpos.cc:1185 — 传入 `var[i]`
     - ppp.cc:1146 — 传入 `var_rs[i]`
     - ins-doppler.cc:180 — 检查并传入 `var[i]`

2. **gettgd() 增加 type 参数 + prange() BDS-3 分码**
   - gettgd(): 从 pntpos.cc 的 static 函数提升为 rtkcmn.cc 全局函数
   - 签名: `gettgd(int sat, const nav_t *nav, int type)`
   - 新增 `getseleph(int sys)`（ephemeris.cc）用于 GAL BGD 选择
   - prange() BDS-3 TGD 分码: B1I/B1Cp/B1Cd 分别取不同 tgd 索引
   - GAL BGD 选择: F/NAV → tgd[0], I/NAV → tgd[1]

3. **ddres() 电离层缩放 lam_carr → sat2freq**
   - rtkpos.cc:1565:
     ```c
     // 修改前
     fi=lami/lam_carr[0]; fj=lamj/lam_carr[0];
     // 修改后
     fi=FREQ1/sat2freq(sat[i],obs[iu[i]].code[ff],nav);
     fj=FREQ1/sat2freq(sat[j],obs[iu[j]].code[ff],nav);
     ```

---

### Step 3：SNR 单位迁移

**涉及文件**: `include/navlib.h`, `solution.cc`, `rinex.cc`, `rinex-rt.cc`, `novatel.cc`, `rtcm3.cc`, `septentrio.cc`, `ppp.cc` 等

**修改清单**:

1. **navlib.h 类型变更**
   - `obsd_t.SNR[]`: unsigned char → uint16_t
   - `ssat_t.snr[]`: unsigned char → uint16_t
   - `lexmsg_t.snr`: unsigned char → uint16_t

2. **所有赋值处改为 SNR_UNIT 制**
   - 模式: `(unsigned char)(val*4.0+0.5)` → `(uint16_t)(val/SNR_UNIT+0.5)`
   - 影响文件: solution.cc(1380), rinex-rt.cc(298), novatel.cc(3处), rtcm3.cc(1949) 等

3. **所有读取处理处**
   - 模式: `ssat->snr[f]*0.25` → `ssat->snr[f]*SNR_UNIT`
   - 影响文件: solution.cc(3处), ppp.cc(503) 等

---

### Step 4：RTK/SPP 剩余迁移 + nav->lam 移除

**涉及文件**: `rtkpos.cc`, `ppp.cc`, `rtkcmn.cc`, `ar.cc`, `ppp_ar.cc`, `rtcm3.cc`, `rcvraw.cc`, `crescent.cc`

**修改清单**:

1. **zdres() 改用 sat2freq**
   - rtkpos.cc:1112-1127 — zdres_sat() 中 `nav->lam` → `sat2freq`

2. **GF 周跳检测合并**
   - rtkpos.cc:843-950 — `detslp_gf_L1L2()` + `detslp_gf_L1L5()` → 通用 `detslp_gf()`

3. **PPP sat2freq 迁移**
   - ppp.cc:473,482,496,755,834,1137 — 6 处 `nav->lam` → `sat2freq`

4. **lam_carr 残留迁移**
   - ar.cc(8处), ppp_ar.cc(2处), rtcm3.cc(4处), rcvraw.cc(1处), crescent.cc(8处)
   - 一般替换模式: `lam_carr[0]` → `CLIGHT/sat2freq(sat, code, nav)`

5. **nav_t.lam 赋值移除**
   - rtkcmn.cc:3225,3234 — 删除 `nav->lam[i][j]=satwavelen(...)` 赋值

---

### Step 5：清理 + RINEX 2.x

**涉及文件**: `rtkcmn.cc`, `rinex-rt.cc`, `include/navlib.h`, `rinex.cc`, `rcvraw.cc`

**修改清单**:

1. **删除废弃代码**
   - 删除 `lam_carr[]` 全局变量（rtkcmn.cc:183）
   - 删除 `satwavelen()` 函数（rtkcmn.cc:4044）
   - 从 nav_t 删除: `leaps`, `lam[][]`, `glo_cpbias`
   - 更新 `nav->lam` → `sat2freq` 在各文件残留处

2. **RINEX 2.x 实时流支持（rinex-rt.cc）**
   - 新增 convcode() 函数（参考 rinex.cc:201 / rtklib_b34/rinex.c:263-346）
   - decode_obsh() 新增 ver 参数和 2.x 头部解析
   - decode_obsepoch() 新增 ver.2 历元解析分支
   - decode_obsdata() 新增 ver.2 数据行处理（80 列换行）
   - input_rinex() 增加版本检测和分发

## 风险与缓解

| 风险 | 可能性 | 缓解措施 |
|------|--------|----------|
| Step 1 常量增大导致内存相关 bug | 中 | 编译通过后运行，检查 spp-tc.rslt 输出 |
| Step 2 算法迁移导致定位结果变差 | 中 | 只检查行数不检查结果质量，允许数值变化 |
| Step 3 SNR 类型变更导致编译错误 | 低 | 全局搜索 `unsigned char.*snr` 和 `*4.0+0.5` 确保全覆盖 |
| Step 4 lam_carr 迁移遗漏 | 中 | 全局搜索 `lam_carr` 确认零残留 |
| Step 5 nav_t 字段删除后链接错误 | 低 | 搜索 `nav->lam`、`nav->leaps`、`nav->glo_cpbias` 确认全覆盖 |

## 验证标准

- 每步编译通过
- `a-cpt/spp-tc.rslt` 行数 ≥ 200000
- 无段错误/运行时崩溃
- 进程可正常 kill
