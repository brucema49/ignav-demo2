# 组合导航更新与抗差估计

该分支完成：①完成ignav GNSS部分的更新（更新到b34版本）、放弃视觉部分和PPP部分。②组合导航的抗差估计


## spp-ins紧组合

原版本不支持spp-ins紧组合（在数据时间对齐阶段，无论什么模式，只有当基准站和流动站的数据存在并且对齐时才会进入下一个流程），已做修改，使得仅有流动站，也可以做spp-ins紧组合,修改如下

```cpp
/* time alignment for observation and imu data-------------------------------*/
static int imuobsalign(rtksvr_t *svr)
{
    int i,j,k,n; double sow1,sow2,sow3;
    obs_t *p1=NULL,*p2=NULL;
    syn_t *psyn=&svr->syn;

    // observation and imu data time alignment 
    n=psyn->of[2]?MAXIMUBUF:psyn->ni;
    p1=svr->obs[0];
    p2=svr->obs[1];
    double dttol=1.0 / svr->rtk.opt.insopt.hz /2;
    for (i=0;i<n&&svr->syn.tali[2]!=2;i++) { // start time alignment 当imu数据存在时且对齐标志不为2

        sow1=time2gpst(svr->imu[i].time,NULL);

        //match rover observation 
        for (j=0;j<(psyn->of[0]?MAXOBSBUF:psyn->nr);j++) {
            sow2=time2gpst(p1[j].data[0].time,NULL);
            if (p1[j].n) {
                if (fabs(sow1-sow2)>dttol) continue;
            }
            psyn->imu    =i;
            psyn->rover  =j;
            psyn->tali[2]=1;
            break;
        }
        if(psyn->tali[2]==1&&svr->rtk.opt.insopt.tc==INSTC_SINGLE) {//当只有imu和rover数据时
            tracet(3,"imu and rover align ok\n");
            psyn->tali[2]=2;//对其标志为2
            return 1;
        }
        
        //match base observation 
        if (psyn->tali[2]==1) {
            for (k=0;k<(psyn->of[1]?MAXOBSBUF:psyn->nb);k++) {
                sow3=time2gpst(p2[k].data[0].time,NULL);
                if (p2[k].n) {
                    if (fabs(sow2-sow3)>DTTOLM) continue;
                }
                else continue;
                psyn->base   =k;
                psyn->tali[2]=2;
                break;
            }
        }
        if (psyn->tali[2]==2) {
            tracet(3,"imu and rover/base align ok\n");
            return 1;
        }
        else psyn->tali[2]=0; //fail 
    }
    return 0;
}
```

## b34更新应用

