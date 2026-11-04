import numpy as np
from numba import njit

@njit(cache=True)
def box_fit(A,y,lo,hi):
 n,d=A.shape;c=(lo+hi)/2;rad=(hi-lo)/2;X=A*rad
 b=y-A@c
 # primal feasible active-set bounded least squares in scaled coordinates
 x=np.zeros(d);active=np.zeros(d,np.int64)
 for iteration in range(100):
  free=np.where(active==0)[0]
  if len(free)>0:
   rhs=b.copy()
   for j in range(d):
    if active[j]!=0:rhs-=X[:,j]*x[j]
   XF=np.empty((n,len(free)))
   for k in range(len(free)):XF[:,k]=X[:,free[k]]
   sol=np.linalg.lstsq(XF,rhs,rcond=1e-12)[0]
   target=x.copy()
   for k in range(len(free)):target[free[k]]=sol[k]
   alpha=1.;hit=-1;side=0
   for j in free:
    if target[j]>1.+1e-10:
     a=(1.-x[j])/(target[j]-x[j])
     if a<alpha:alpha=max(0.,a);hit=j;side=1
    elif target[j]<-1.-1e-10:
     a=(-1.-x[j])/(target[j]-x[j])
     if a<alpha:alpha=max(0.,a);hit=j;side=-1
   x=x+alpha*(target-x)
   if hit>=0:
    x[hit]=side;active[hit]=side
    continue
  gradient=X.T@(X@x-b)
  release=-1;worst=1e-9
  for j in range(d):
   # at upper bound gradient<=0; lower bound gradient>=0
   violation=active[j]*gradient[j]
   if violation>worst:worst=violation;release=j
  if release<0:
   r=A@(c+rad*x)-y
   return np.sqrt(np.mean(r*r)),c+rad*x,iteration+1
  active[release]=0
 raise ValueError('bounded least squares failed to converge')

if __name__=='__main__':
 from scipy.optimize import lsq_linear
 import time
 rng=np.random.default_rng(17888);worst=0.;start=time.perf_counter()
 for d in (3,4):
  for k in range(200):
   a=rng.normal(size=(20,d))*rng.uniform(.01,5,d);y=rng.normal(size=20)
   if k%7==0:a[:,1]=a[:,0]
   l=np.full(d,-1.);h=np.full(d,1.)
   s,p,it=box_fit(a,y,l,h);ref=lsq_linear(a,y,bounds=(l,h),method='bvls',tol=1e-10)
   delta=abs(s-np.sqrt(np.mean((a@ref.x-y)**2)));worst=max(worst,delta)
   assert delta<1e-8,(d,k,s,ref.cost,it)
 print('400 reference fits passed',worst,'seconds',time.perf_counter()-start)
