using DelayDiffEq
using Plots;gr()
##.
function IsTailDrop(Xᵢ,sᵢ)
    if Xᵢ >= sᵢ
        true
    else
        false
    end
end

function IsEmpty(Xᵢ)
    if Xᵢ > 0
        false
    else
        true
    end
end

# constant
ϵ=25/1000
P=0.3
τ₃₁=30/1000
τ₁₂=20/1000
τ₂₄=50/1000
# ϵ: a timer interval to invoke retransmission request
# P: P(2,3) the random packet lost ratio (lastmile link)
# τ₃₁: the transmission time from M₃ to M₁
# τ₁₂: the transmission time from M₁ to M₂
# τ₂₄: the transmission time from M₂ to M₄

μ₁=35
s₁=80
μ₂=15
s₂=20
p=(μ₁,μ₂,s₁,s₂)

global N=60
global RexferN=ceil(N*P/(1-P))
X₁=N
X₂=0
X₃=0
X₄=0
X₅=0
r₁=0
r₂=0
delayed_r₂=0
z₀=τ₃₁+τ₁₂+τ₂₄
delayed_z₀=τ₃₁+τ₁₂+τ₂₄
u₀=[X₁,X₂,X₃,X₄,X₅,r₁,r₂,delayed_r₂,z₀,delayed_z₀]

function h_QN(p,t; idxs::Union{Nothing,Integer}=nothing)
    t ≤ 0 || error("history function is only implemented for t ≤ 0")

    if idxs === nothing
      u₀
    elseif idxs == 1
      X₁
    elseif idxs == 9 || idxs == 10
      z₀
    else
      zero(t)
    end
end


function f_QN(du,u,h,p,t)
  # state variables
  X₁,X₂,X₃,X₄,X₅,r₁,r₂,delayed_r₂,z,delayed_z=u
  # X₁: M₁ queue length (media server)
  # X₂: M₂ queue length (lastmile link)
  # X₃: M₃ queue length (lost packet list)
  # X₄: M₄ queue length (receive packet list)
  # X₅: M₅ queue length (historical retransmission request packet list)
  # r₁: the waiting time in M₁ queue for arrival (media server)
  # r₂: the waiting time in M₂ queue for arrival (lastmile link)
  # z: the retransmission round-trip-time for arrival (receive packet list)
  
  # parameters
  μ₁,μ₂,s₁,s₂=p
  # μ₁: packet per second, the service rate of M₁ (media server)
  # μ₂: packet per second, the service rate of M₂ (lastmile link)
  # s₁: the queue buffer limit of M₁ (media server)
  # s₂: the queue buffer limit of M₂ (lastmile link)

  # transition rates
  if first_request == true && IsEmpty(X₁) && IsEmpty(X₂)
    global Q[3,5]=1/ϵ * max(0, h(p,t-z; idxs=3) )
    println("initial request! Q[3,5]=",Q[3,5],",z=",z,",t=",t)
    global first_request = false
    global t₋=t
  elseif t-t₋ >= ϵ
    if z < delayed_z+ϵ && X₅ <= RexferN
      global Q[3,5]=1/ϵ * max(0, h(p,t-z; idxs=3)-h(p,t-delayed_z-ϵ; idxs=3) )
      print("111 update")
      print(" Q[3,5]=",Q[3,5])
      println(",Δt=",t-t₋)
    else
      global Q[3,5]=0.0
      print("000 update")
      print(" Q[3,5]=",Q[3,5])
      println(",Δt=",t-t₋)
    end
    global t₋=t
  end
  global Q[3,1]=Q[3,5]
  global Q[1,3]=Q[3,1] * convert(Int, IsTailDrop(X₁, s₁))
  global Q[1,2]=μ₁ * (1 - convert(Int, IsEmpty(X₁)))
  global Q[2,3]=μ₁ * (1 - convert(Int, IsEmpty(X₁))) * convert(Int, IsTailDrop(X₂, s₂)) + μ₂ * (1 - convert(Int, IsEmpty(X₂))) * P
  global Q[2,4]=μ₂ * (1 - convert(Int, IsEmpty(X₂))) * (1 - P)
  #if first_request == false
  #  print("Q[3,5]=",Q[3,5])
  #  print(",Q[1,3]=",Q[1,3])
  #  print(",Q[1,2]=",Q[1,2])
  #  print(",Q[2,3]=",Q[2,3])
  #  println(",Q[2,4]=",Q[2,4])
  #end

  # fluid approximation of qn_model
  du[1]=dX₁=-Q[1,3]-Q[1,2]+Q[3,1]
  du[2]=dX₂=-Q[2,3]-Q[2,4]+Q[1,2]
  du[3]=dX₃=-zero(Q[3,1])-zero(Q[3,5])+Q[1,3]+Q[2,3]
  du[4]=dX₄=Q[2,4]
  du[5]=dX₅=Q[3,5]

  # auxiliary state variables
  new_r₁=1/μ₁ * max(0,h(p,t-r₁; idxs=1))
  new_r₂=1/μ₂ * max(0,h(p,t-r₂; idxs=2))
  new_delayed_r₂=h(p,t-τ₂₄; idxs=7)
  new_delayed_z=h(p,t-ϵ; idxs=9)
  new_z=τ₃₁ + h(p,t-τ₂₄-delayed_r₂-τ₁₂; idxs=6) + τ₁₂ + delayed_r₂ + τ₂₄
  du[6]=new_r₁ - r₁
  du[7]=new_r₂ - r₂
  du[8]=new_delayed_r₂ - delayed_r₂
  du[9]=new_z - z
  du[10]=new_delayed_z - delayed_z
end

lag1=(u,p,t)->u[9] #t-z
lag2=(u,p,t)->u[10]+ϵ #t-delayed_z-ϵ
lag3=(u,p,t)->u[6] #t-r₁
lag4=(u,p,t)->u[7] #t-r₂#t-τ₂₄
lag5=(u,p,t)->τ₂₄+u[8]+τ₁₂ #t-τ₂₄-delayed_r₂-τ₁₂

tspan=(0.0,10.0)
tstep=tspan[1]:1/1000:tspan[2]

global first_request=true
global Q=zeros(5,5)
global t₋=Inf
qn_problem=DDEProblem(f_QN,u₀,h_QN,tspan,p; constant_lags=(τ₂₄,ϵ,), dependent_lags=(lag1,lag2,lag3,lag4,lag5))
qn_solution=solve(qn_problem,MethodOfSteps(Tsit5()),dt=5/1000, adaptive=false)
println("solver finished!")

##.
states=length(u₀)
plot(qn_solution.t*ones(1,states),transpose(qn_solution),size=(800,1200),layout=grid(states,1,heights=ones(states)/states),label=[ "X₁" "X₂" "X₃" "X₄" "X₅" "r₁" "r₂" "delayed_r₂" "z" "delayed_z"])
savefig("images/qn_solution.svg")