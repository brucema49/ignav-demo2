# NavLib - INS/GNSS 集成导航系统

基于ignav的NavLib是一个用于车辆定位的集成导航系统，结合了惯性导航系统(INS)、全球导航卫星系统(GNSS)导航技术。该系统支持实时动态(RTK)定位、紧耦合/松耦合INS-GNSS集成，并包含先进的欺骗检测功能。

## 目录

- [NavLib - INS/GNSS 集成导航系统](#navlib---insgnss-集成导航系统)
  - [目录](#目录)
  - [系统特性](#系统特性)
  - [编译安装](#编译安装)
    - [系统要求](#系统要求)
    - [依赖库](#依赖库)
    - [编译步骤](#编译步骤)
  - [运行使用](#运行使用)
    - [基本运行命令](#基本运行命令)
    - [程序说明](#程序说明)
  - [配置文件详解](#配置文件详解)
    - [配置文件结构](#配置文件结构)
    - [欺骗检测功能配置](#欺骗检测功能配置)
      - [核心配置参数](#核心配置参数)
      - [统计参数配置](#统计参数配置)
    - [输入输出配置](#输入输出配置)
      - [输入流配置示例](#输入流配置示例)
      - [输出配置](#输出配置)
    - [INS参数配置](#ins参数配置)
      - [基本INS设置](#基本ins设置)
      - [INS不确定性参数](#ins不确定性参数)
  - [欺骗检测功能](#欺骗检测功能)
    - [窗口化统计检测器 (Windowed Statistic Detector)](#窗口化统计检测器-windowed-statistic-detector)
      - [工作原理](#工作原理)
      - [数学原理](#数学原理)
      - [配置参数](#配置参数)
    - [窗口化新息检测器 (Windowed Innovation Detector)](#窗口化新息检测器-windowed-innovation-detector)
      - [工作原理](#工作原理-1)
      - [工作模式](#工作模式)
      - [数学原理](#数学原理-1)
      - [配置参数](#配置参数-1)
    - [配置参数说明](#配置参数说明)
      - [窗口大小](#窗口大小)
      - [检测阈值](#检测阈值)
      - [输出内容](#输出内容)
  - [示例数据](#示例数据)
  - [项目结构](#项目结构)
    - [调试技巧](#调试技巧)

## 系统特性

- **多系统集成**: 支持INS、GNSS、视觉传感器的紧耦合和松耦合集成
- **高精度定位**: 支持RTK、PPP等多种定位模式
- **欺骗检测**: 内置两种GNSS欺骗信号检测算法
- **多传感器支持**: 支持IMU、相机、里程计等多种传感器
- **实时处理**: 支持实时数据流处理和离线数据处理
- **跨平台**: 基于C++开发，支持Linux系统

## 编译安装

### 系统要求

- Linux 操作系统
- CMake 2.8 或更高版本
- C++11 兼容编译器

### 依赖库

系统需要以下数学计算库：

- **BLAS** (Basic Linear Algebra Subprograms)
- **LAPACK** (Linear Algebra Package)

在Ubuntu系统上安装依赖：

```bash
sudo apt-get update
sudo apt-get install build-essential cmake libblas-dev liblapack-dev zlib1g-dev
```

### 编译步骤

1. **克隆项目** (如果尚未克隆)

```bash
git clone <repository-url>
cd navlib
```

1. **创建构建目录并编译**

```bash
mkdir build && cd build
cmake ..
make 
```

1. **安装到系统** (可选)

```bash
sudo make install
```

编译完成后，可执行文件将生成在 `bin/` 目录下，库文件在 `lib/` 目录下。

## 运行使用

### 基本运行命令

```bash
# 基本运行格式
./bin/navapp -o <配置文件路径> -m <端口号>

# 示例：使用示例配置文件运行
./bin/navapp -o ../example/conf/navlib.conf 

# 其他可用程序
./bin/lc-rts    # 松耦合RTS平滑处理
./bin/lc-fbsm   # 松耦合前向后向平滑处理
```

### 程序说明

- **navapp**: 主程序，支持实时和离线处理
- **lc-rts**: 松耦合RTS(Rauch-Tung-Striebel)平滑器
- **lc-fbsm**: 松耦合前向后向平滑器

## 配置文件详解

### 配置文件结构

配置文件采用键值对格式，主要分为以下几个部分：

1. **控制台设置** (`console-*`): 控制台输出格式和密码
2. **定位参数** (`pos1-*`, `pos2-*`): 定位模式、频率、掩角等
3. **输出设置** (`out-*`): 输出格式、内容选项
4. **欺骗检测** (`spoofing-*`, `stats-*`): 欺骗检测相关参数
5. **天线参数** (`ant1-*`, `ant2-*`): 天线位置和类型
6. **输入流设置** (`inpstr*-*`): 数据输入源配置
7. **输出流设置** (`outstr*-*`): 数据输出配置
8. **INS参数** (`ins-*`): 惯性导航系统参数
9. **其他设置** (`file-*`): 文件路径
10. **卫星系统** 默认使用GPS系统和北斗2代，不支持北斗3代

### 欺骗检测功能配置

#### 核心配置参数

```ini
# 欺骗检测器选项 (0:关闭, 1:窗口化统计检测, 2:窗口化新息检测)
spoofing-detector = 2

# 欺骗检测输出选项 (0:关闭, 1:窗口化统计, 2:窗口化新息)
out-spoofing = 2
```

#### 统计参数配置

```ini
# 误差比率参数
stats-eratio1 = 100
stats-eratio2 = 100

# 相位误差参数 (米)
stats-errphase = 0.005
stats-errphaseel = 0.005
stats-errphasebl = 0

# 多普勒误差 (Hz)
stats-errdoppler = 1

# 标准差参数
stats-stdbias = 30          # 偏差标准差 (米)
stats-stdiono = 0.01        # 电离层标准差 (米)
stats-stdtrop = 0.3         # 对流层标准差 (米)

# 过程噪声参数
stats-prnaccelh = 0.1       # 水平加速度过程噪声 (m/s^2)
stats-prnaccelv = 0.03      # 垂直加速度过程噪声 (m/s^2)
stats-prnbias = 0.03        # 偏差过程噪声 (米)
stats-prniono = 0.001       # 电离层过程噪声 (米)
stats-prntrop = 0.001       # 对流层过程噪声 (米)
stats-prnpos = 0            # 位置过程噪声 (米)
stats-clkstab = 5e-12       # 时钟稳定性 (s/s)
```

### 输入输出配置

#### 输入流配置示例

```ini
# 流动站数据 (RINEX格式)
inpstr1-type = file
inpstr1-path = /path/to/rover/171107134322.17o
inpstr1-format = rinex

# 基站数据
inpstr2-type = file
inpstr2-path = /path/to/base/5328K44285201711070000A.17O
inpstr2-format = rinex

# IMU数据 (M39格式)
inpstr5-type = file
inpstr5-path = /path/to/rover/171107134322.imu
inpstr5-format = m39
```

#### 输出配置

```ini
# 解决方案输出
outstr1-type = file
outstr1-path = ../conf/spp_tc_data3_sol1.txt
outstr1-format = xyz

# 输出内容控制
out-solformat = xyz          # 输出格式
out-outhead = on            # 输出头部信息
out-outopt = on             # 输出选项
out-att = 0                 # 姿态输出 (0:否, 1:是)
out-acc = 0                 # 加速度输出
out-vel = 0                 # 速度输出
out-spoofing = 2            # 欺骗检测输出
```

### INS参数配置

#### 基本INS设置

```ini
# 紧耦合模式，spp-tc仅支持单频
pos1-posmode = ins-tightly-coupled

# IMU参数
ins-hz = 200.0              # IMU采样频率 (Hz)
ins-imuformat = 2           # IMU数据格式 (1:KVH, 2:GI310-m39, 3:ublox-EVK-M8U)
ins-imucoors = 2            # IMU坐标系 (1:FRD, 2:RFU)

# 杆臂参数 (从GPS天线到INS，FRD坐标系)
ins-leverarm1 = 0.383       # X方向 (米)
ins-leverarm2 = -0.163      # Y方向 (米)
ins-leverarm3 = -0.940      # Z方向 (米)
```

#### INS不确定性参数

```ini
# 初始不确定性
ins-uncatt = 0.00174532922  # 初始姿态不确定性 (弧度)
ins-uncvel = 30.0           # 初始速度不确定性 (米/秒)
ins-uncpos = 30.0           # 初始位置不确定性 (米)
ins-uncba = 9.80665E-3      # 加速度计偏置不确定性 (m/s^2)
ins-uncbg = 4.8481367284e-05 # 陀螺仪偏置不确定性 (弧度/秒)

# 过程噪声谱密度
ins-psd_gyro = 5.72003802085e-09  # 陀螺仪噪声PSD (rad^2/s)
ins-psd_accl = 2.33611111111e-07  # 加速度计噪声PSD (m^2 s^-3)
ins-psd_ba = 1E-7                  # 加速度计偏置随机游走PSD (m^2 s^-5)
ins-psd_bg = 2E-12                 # 陀螺仪偏置随机游走PSD (rad^2 s^-3)
```

## 欺骗检测功能

NavLib 实现了两种先进的GNSS欺骗信号检测算法，并全面支持多系统（GPS, GLONASS, Galileo, BDS 等）。

### 使用方法

通过修改配置文件中的以下参数开启欺骗检测：

```ini
# 欺骗检测器选项 (0:关闭, 1:窗口化统计检测WS, 2:窗口化新息检测WI)
spoofing-detector = 2

# 欺骗检测输出选项 (0:关闭, 1:输出WS统计量, 2:输出WI统计量,需与上面对应)
out-spoofing = 2

# 窗口大小设置 (推荐范围1~10，最大支持10)
# windowed_size = 10 
```

注意：支持多系统欺骗检测时可以在定位参数中开启所有需要的导航系统星座，比如 `pos1-navsys=63`（所有系统）。当前欺骗检测在紧组合模式单频处理（`pos1-posmode=ins-tightly-coupled`）下生效。

### 输出结果查看

开启欺骗检测并设置输出选项后，运行结果的 `.txt` 后缀输出文件中将会追加欺骗检测的对应统计量（WS或WI值）。

用户可以基于卡方分布的阈值判断是否发生欺骗：
- 提取追加输出对应列的统计量数值。
- 根据各历元的跟踪卫星数量（或自由度），计算卡方分布置信区间（例如99%或99.9%）。
- 若统计量显著超过卡方分布判定阈值，则指示可能出现欺骗。

## 示例数据

## 项目结构

### 调试技巧

- 启用调试模式：`cmake -DCMAKE_BUILD_TYPE=Debug ..`
- 查看跟踪输出：配置文件中的 `file-tracefile` 选项
- 使用Valgrind进行内存检查
