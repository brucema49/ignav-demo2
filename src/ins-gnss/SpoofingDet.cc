#include "../../include/navlib.h"


/*借鉴filter函数处理P阵和H阵，将最后的A阵存储在sol->CovA*/
int ProcessWsPH(WindowedResiduals *windowed_residuals,const double *P,const double *H,const int n,const int m){
    
    double *P_,*H_,*R,*temp;
    int i,j,k,*ix;
    int nv=windowed_residuals->epoch_data[windowed_residuals->current_index].residuals.size();//当前历元有效残差维度

    ix=imat(n,1); for (i=k=0;i<n;i++) {
        if (P[i+i*n]>0.0) ix[k++]=i;//仅确保P阵对角线元素大于0
    }
    P_=mat(k,k);H_=mat(k,m);
    for (i=0;i<k;i++) {
        for (j=0;j<k;j++) P_[i+j*k]=P[ix[i]+ix[j]*n];
        for (j=0;j<m;j++) H_[i+j*k]=H[ix[i]+j*n];
    }
    double *Q=mat(nv,nv);
    R=zeros(nv,nv);temp=zeros(k,nv);
    for (i=0;i<nv;i++) R[i+i*nv]=windowed_residuals->epoch_data[windowed_residuals->current_index].cov_diag[i];
    matcpy(Q,R,nv,nv);
    matmul("NN",k,nv,k,1.0,P_,H_,0.0,temp);
    matmul("TN",nv,nv,k,1.0,H_,temp,1.0,Q);
    
    //存储协方差矩阵
    windowed_residuals->epoch_data[windowed_residuals->current_index].CovA.clear();//清空A阵
    for(i=0;i<nv*nv;i++) windowed_residuals->epoch_data[windowed_residuals->current_index].CovA.push_back(Q[i]);
    if(windowed_residuals->valid_count<10) windowed_residuals->valid_count++;//有效历元数更新

    free(ix);free(temp);free(R);
    free(P_); free(H_);free(Q); 
    return 0;
}

/*the windowed statistic detector*/
void ChiSquareTestWS(WindowedResiduals *windowed_residuals,const double* P,const double* H,const int nx,const int m){
 
    ProcessWsPH(windowed_residuals,P,H,nx,m);//计算并存储协方差矩阵A
    if(windowed_residuals->valid_count==windowed_residuals->windows_size){//达到窗口数,进行统计
        double sum=0.0;

        for(int i=0;i<windowed_residuals->valid_count;i++){
            double *gamma,*A,*temp;
            double lambda=0.0;
            int n=windowed_residuals->epoch_data[i].residuals.size();//残差数量
            gamma=zeros(n,1);//初始化新息矩阵
            A=mat(n,n);//初始化协方差矩阵
            temp=zeros(1,n);
            for(int j=0;j<n;j++){
                gamma[j]=windowed_residuals->epoch_data[i].residuals[j];//新息赋值
                for(int k=0;k<n;k++) A[k+j*n]=windowed_residuals->epoch_data[i].CovA[k+j*n];//协方差矩阵赋值
            }

            // 在存储或使用前确保对称性
            for (int i = 0; i < n; i++) {
                for (int j = i+1; j < n; j++) {
                    double avg = 0.5 * (A[i*n+j] + A[j*n+i]);
                    A[i*n+j] = A[j*n+i] = avg;
                }
            }

            int info = matinv(A, n);
            if (info != 0) {
                // 求逆失败，跳过这个历元
                free(gamma); free(A); free(temp);
                continue;
            }
            matmul("NN",1,n,n,1.0,gamma,A,0.0,temp);//计算统计量
            matmul("NN",1,1,n,1.0,temp,gamma,0.0,&lambda);
            sum+=lambda;

            free(gamma);free(A);free(temp);
        }
        windowed_residuals->ws=sum;
    }
}

/*存储H和P,不在存储A*/
int ProcessWiPH(WindowedResiduals *windowed_residuals,const double *P,const double *H,const int nx){
    
    int nv=windowed_residuals->epoch_data[windowed_residuals->current_index].residuals.size();//当前历元有效残差维度

    windowed_residuals->epoch_data[windowed_residuals->current_index].H.clear();
    windowed_residuals->epoch_data[windowed_residuals->current_index].P.clear();
    for(int i=0;i<nv;i++) for(int j=0;j<nx;j++) windowed_residuals->epoch_data[windowed_residuals->current_index].H.push_back(H[j+i*nx]);
    for(int i=0;i<nx;i++) for(int j=0;j<nx;j++) windowed_residuals->epoch_data[windowed_residuals->current_index].P.push_back(P[j+i*nx]);
    
    if(windowed_residuals->valid_count<10) windowed_residuals->valid_count++;//有效历元数更新

    return 0;
}
//计算每个历元的A矩阵
int computeWiA(WindowedResiduals *windowed_residuals,const int nx,const int n){
    int i,j;
    int nv=n;//当前历元有效残差维度

    for(int epoch=0;epoch<windowed_residuals->valid_count;epoch++){
        double *R,*temp;
        double *P=mat(nx,nx),*H=mat(nx,nv);
        for (i=0;i<nx;i++) {
            for (j=0;j<nx;j++) P[j+i*nx]=windowed_residuals->epoch_data[epoch].P[j+i*nx];
            for (j=0;j<nv;j++) H[i+j*nx]=windowed_residuals->epoch_data[epoch].H[i+j*nx];
        }
        double *Q=mat(nv,nv);
        R=zeros(nv,nv);temp=zeros(nx,nv);
        for (i=0;i<nv;i++) R[i+i*nv]=windowed_residuals->epoch_data[epoch].cov_diag[i];
        matcpy(Q,R,nv,nv);
        matmul("NN",nx,nv,nx,1.0,P,H,0.0,temp);
        matmul("TN",nv,nv,nx,1.0,H,temp,1.0,Q);
    
        //存储协方差矩阵
        windowed_residuals->epoch_data[epoch].CovA.clear();
        for(i=0;i<nv*nv;i++) windowed_residuals->epoch_data[epoch].CovA.push_back(Q[i]);

        free(temp);free(R);
        free(P); free(H);free(Q); 
    }
    return 0;
}

//计算每个历元中相同卫星的残差索引,返回相同卫星数量
int computeIndexSat(WindowedResiduals *windowed_residuals, std::array<std::vector<int>, 10> &SatInd) {
    // 清空结果容器
    for (auto& vec : SatInd) {
        vec.clear();
    }
    
    // 步骤1: 找出所有历元中共同的卫星
    std::unordered_set<unsigned char> common_sats;
    
    // 用第一个有效历元初始化共同卫星集合
    const auto& first_epoch = windowed_residuals->epoch_data[0];
    common_sats.insert(first_epoch.sat.begin(), first_epoch.sat.end());
    
    // 与其他历元求交集
    for (int i = 1; i < windowed_residuals->valid_count; ++i) {
        const auto& epoch = windowed_residuals->epoch_data[i];
        std::unordered_set<unsigned char> current_sats(epoch.sat.begin(), epoch.sat.end());
        
        // 求交集
        std::unordered_set<unsigned char> intersection;
        for (auto sat : common_sats) {
            if (current_sats.find(sat) != current_sats.end()) {
                intersection.insert(sat);
            }
        }
        common_sats = std::move(intersection);
        
        // 如果没有共同卫星，提前返回
        if (common_sats.empty()) {
            return 0;
        }
    }
    
    // 步骤2: 为每个历元记录公共卫星的残差索引位置
    int common_sat_count = 0;
    
    for (int i = 0; i < windowed_residuals->valid_count; ++i) {
        const auto& epoch = windowed_residuals->epoch_data[i];
        const auto& sat_vector = epoch.sat;
        
        // 遍历当前历元的所有卫星，记录公共卫星的索引
        for (unsigned int j = 0; j < sat_vector.size(); ++j) {
            if (common_sats.find(sat_vector[j]) != common_sats.end()) {
                SatInd[i].push_back(j);
            }
        }
        
        // 对索引进行排序（如果需要保持特定顺序）
        std::sort(SatInd[i].begin(), SatInd[i].end());
        
        // 更新公共卫星数量（取最小值确保一致性）
        if (i == 0) {
            common_sat_count = SatInd[i].size();
        } else {
            common_sat_count = std::min(common_sat_count, (int)SatInd[i].size());
        }
    }
    return common_sat_count;
}

//追踪动态卫星变化和存储相同卫星索引及其A矩阵
int computeDynamicWi(WindowedResiduals *windowed_residuals,const int nx,std::array<std::vector<int>, 10> &SatInd){
    //计算相同卫星索引，返回相同卫星数量
    int nv=computeIndexSat(windowed_residuals,SatInd);
    //计算每个历元的A矩阵
    for(int epoch=0;epoch<windowed_residuals->valid_count;epoch++){
        double *R,*temp;
        double *P=mat(nx,nx),*H=mat(nx,nv);
        for (int i=0;i<nx;i++) {
            for (int j=0;j<nx;j++) P[j+i*nx]=windowed_residuals->epoch_data[epoch].P[j+i*nx];
            for(int j=0;j<nv;j++) H[i+j*nx]=windowed_residuals->epoch_data[epoch].H[i+SatInd[epoch][j]*nx];//提取相同卫星的H矩阵列
        }
        double *Q=mat(nv,nv);
        R=zeros(nv,nv);temp=zeros(nx,nv);
        for (int i=0;i<nv;i++) R[i+i*nv]=windowed_residuals->epoch_data[epoch].cov_diag[SatInd[epoch][i]];
        matcpy(Q,R,nv,nv);
        matmul("NN",nx,nv,nx,1.0,P,H,0.0,temp);
        matmul("TN",nv,nv,nx,1.0,H,temp,1.0,Q);

        //存储协方差矩阵
        windowed_residuals->epoch_data[epoch].CovA.clear();
        for(int i=0;i<nv*nv;i++) windowed_residuals->epoch_data[epoch].CovA.push_back(Q[i]);

        free(temp);free(R);
        free(P); free(H);free(Q); 
    }
    return nv;
}

/*the windowed innoviation detector   考虑历元间的动态变化,还需存储H和P，不在存储A*/
void ChiSquareTestWI(WindowedResiduals *windowed_residuals,const double* P,const double* H,const int nx,const int m){
    ProcessWiPH(windowed_residuals,P,H,nx);//计算并存储H和P
    int opt=1;       //0:简单提取前n个 1:动态追踪卫星
    if(windowed_residuals->valid_count==windowed_residuals->windows_size && opt==0){//达到窗口数,进行简单模式的统计 
        /*简单版：仅仅使用前n个残差，n为窗口里最小的新息维度*/
        double *sum_AinvGamma,*sum_Ainv,*temp;
        double *gamma,*A,*AinvGamma;
        int n=100;
        for(int i=0;i<windowed_residuals->valid_count;i++) n=MIN(n,(int)windowed_residuals->epoch_data[i].residuals.size());//获取窗口内最小的新息维度

        //根据n计算每个历元的A矩阵
        computeWiA(windowed_residuals,nx,n);

        sum_AinvGamma=zeros(n,1);sum_Ainv=zeros(n,n);temp=zeros(1,n);
        gamma=mat(n,1);//初始化新息矩阵
        A=mat(n,n);//初始化协方差矩阵
        AinvGamma=zeros(n,1);//初始化累加矩阵
        //遍历窗口内每个历元
        for(int i=0;i<windowed_residuals->valid_count;i++){
            for(int j=0;j<n;j++){//赋值
                gamma[j]=windowed_residuals->epoch_data[i].residuals[j];//新息赋值
                for(int k=0;k<n;k++) A[k+j*n]=windowed_residuals->epoch_data[i].CovA[k+j*n];//协方差矩阵赋值
            }
            matinv(A,n);//计算当前历元协方差矩阵的逆
            matmul("NN",n,1,n,1.0,A,gamma,0.0,AinvGamma);//计算统计量n*1

            for(int j=0;j<n;j++){//括号内累加
                sum_AinvGamma[j]+=AinvGamma[j];
                for(int k=0;k<n;k++) sum_Ainv[k+j*n]+=A[k+j*n];
            }
        }
        matinv(sum_Ainv,n);//计算协方差矩阵的逆
        matmul("NN",1,n,n,1.0,sum_AinvGamma,sum_Ainv,0.0,temp);//计算统计量1*n
        double reslt=dot(temp,sum_AinvGamma,n);
        windowed_residuals->wi=reslt;

        free(gamma);free(A);free(AinvGamma);
        free(sum_Ainv);free(sum_AinvGamma);free(temp);

        //达到窗口数,进行动态模式的统计
    }else if(windowed_residuals->valid_count==windowed_residuals->windows_size && opt==1){ 
        /*动态版：追踪每个历元的卫星编号，提取相同卫星的残差进行统计*/
        //TODO
        double *sum_AinvGamma,*sum_Ainv,*temp;
        double *gamma,*A,*AinvGamma;
        std::array<std::vector<int>, 10> SatInd; 
        //计算相同卫星索引及其A矩阵
        int n=computeDynamicWi(windowed_residuals,nx,SatInd);
        windowed_residuals->commonSatNumberWi=n;
        sum_AinvGamma=zeros(n,1);sum_Ainv=zeros(n,n);temp=zeros(1,n);
        gamma=mat(n,1);//初始化新息矩阵
        A=mat(n,n);//初始化协方差矩阵
        AinvGamma=zeros(n,1);//初始化累加矩阵
        //遍历窗口内每个历元
        for(int i=0;i<windowed_residuals->valid_count;i++){
            for(int j=0;j<n;j++){//赋值
                gamma[j]=windowed_residuals->epoch_data[i].residuals[SatInd[i][j]];//新息赋值
                for(int k=0;k<n;k++) A[k+j*n]=windowed_residuals->epoch_data[i].CovA[k+j*n];//协方差矩阵赋值
            }
            int info = matinv(A, n);
            if (info != 0) {
                // 求逆失败，跳过这个历元
                free(gamma); free(A); free(temp);
                continue;
            }
            matmul("NN",n,1,n,1.0,A,gamma,0.0,AinvGamma);//计算统计量n*1

            for(int j=0;j<n;j++){//括号内累加
                sum_AinvGamma[j]+=AinvGamma[j];
                for(int k=0;k<n;k++) sum_Ainv[k+j*n]+=A[k+j*n];
            }
        }
        matinv(sum_Ainv,n);//计算协方差矩阵的逆
        matmul("NN",1,n,n,1.0,sum_AinvGamma,sum_Ainv,0.0,temp);//计算统计量1*n
        double reslt=dot(temp,sum_AinvGamma,n);
        windowed_residuals->wi=reslt;

        free(gamma);free(A);free(AinvGamma);
        free(sum_Ainv);free(sum_AinvGamma);free(temp);

    } 
}

// 更新窗口化残差数据以进行欺骗检测,仅支持单频,实际当第11的历元才会解算，偶然解决第一个历元的用的是后验残差的问题
EXPORT int SpoofingDetection(const prcopt_t *opt,sol_t *sol, const double* v, const double *var,const int nv,const int nx,const double *P,const double *H) {
    sol->windowed_residuals.windows_size=10;
    int opts=opt->spoofing_detector;        //1:the windowed statistic detector   2:the windowed innoviation detector
    if(opts==0) return 0;

    sol->windowed_residuals.total_residuals-=sol->windowed_residuals.epoch_data[sol->windowed_residuals.current_index].residuals.size();//总残差-旧残差
    sol->windowed_residuals.epoch_data[sol->windowed_residuals.current_index].residuals.clear();
    sol->windowed_residuals.epoch_data[sol->windowed_residuals.current_index].cov_diag.clear();
    for(int i=0;i<nv&&v[i]!=0.0;i++) {
            sol->windowed_residuals.epoch_data[sol->windowed_residuals.current_index].residuals.push_back(v[i]);
            sol->windowed_residuals.epoch_data[sol->windowed_residuals.current_index].cov_diag.push_back(var[i]);
        }
    //总残差数更新
    sol->windowed_residuals.total_residuals+=sol->windowed_residuals.epoch_data[sol->windowed_residuals.current_index].residuals.size();
    //the windowed statistic detector
    if(opts==1)ChiSquareTestWS(&sol->windowed_residuals,P,H,nx,nv);
    //the windowed innoviation detector
    else if(opts==2)ChiSquareTestWI(&sol->windowed_residuals,P,H,nx,nv);

    if (++sol->windowed_residuals.current_index>9) sol->windowed_residuals.current_index-=10;//窗口环形索引
    
    return 0;
}
