*Location of intput files
$setglobal datadir                data/
$setglobal DataIn                 InputData

*Location of output files
$setglobal output_dir   results/
$setglobal result       Results_240713

sets
s   storage  /PSP,Bat_1,Bat_2/
t   time    /t1*t17544/
h   hour    /h1*h24/


*t17544
scen price scenario
map_TH(t,h) time mapping
tlast(t)
hlast(h)
;

tlast(t)  = yes$(ord(t) eq card(t));
hlast(h)  = yes$(ord(h) eq card(h));

scalars
cap     turbine_pumping capacity        /1/
;
parameters
priceup upload electricity prices
price(t) wholesale electricity price [EUR per MWh]
real_price(t) actual market price [EUR per MWh]

eta(s)     efficiency of a storage cycle
            /PSP   0.75
             Bat_1 0.8
             Bat_2 0.9 /
ecr(s)     energy capacity ratio
            /PSP   7
             Bat_1 3
             Bat_2 1 /
;

*Data Upload
$onecho > Import.txt
    set=scen           rng=price_scenarios!B2:B100    rdim=1 
    set=map_TH         rng=timemap!B2                 rdim=2
    par=priceup        rng=prices!B2:Z18000           rdim=1 cdim=1
    
$offecho

$onUNDF
*$call GDXXRW I=%datadir%%DataIn%.xlsx O=%datadir%%DataIn%.gdx cmerge=1 @Import.txt
$gdxin %datadir%%DataIn%.gdx
$LOAD scen
$LOAD map_TH
$LOAD priceup
$gdxin
$offUNDF

display scen, priceup, map_TH ;



real_price(t) = priceup(t,'Real Price') ;


Variable
Profit  Profit of the storage unit [EUR]
;

Positive variable
G(s,t)       electricity generation by storage   [MWh per h]
Charge(s,t)  charging storage (electricity consumption) [MWh per h]
SL(s,t)      Storage level [MWh]
;

Equations
    
Obj         Objective Function maximizing profits
StorageLevel     Storage level
Store_Max   maximum storage generation and charging [MWh per h]
Gen_Max     generation is lower than storage level
SL_Max      maximum storage level
SL_hfirst
SL_hlast

;

Obj..   Profit =E= sum((s,t), (G(s,t)-Charge(s,t))*price(t) )
;
Store_Max(s,t)..    G(s,t)+ Charge(s,t) =L= cap
;
Gen_Max(s,t)..      G(s,t) =L= SL(s,t-1)
;
SL_Max(s,t)..    SL(s,t) =L= cap * ecr(s)
;
StorageLevel(s,t,h)$(map_TH(t,h) and ord(h)>1)..        SL(s,t) =E= SL(s,t-1) - G(s,t) + Charge(s,t)*eta(s)
;
*$(ord(t)>=2)


SL_hfirst(s,t)$map_TH(t,'h1')..       SL(s,t) =E= 0* cap * ecr(s) + Charge(s,t)*eta(s) - G(s,t)
;
SL_hlast(s,t)$map_TH(t,'h24')..       SL(s,t) =E= 0* cap * ecr(s)
;



model Storage_Profit /all/
;


Parameter
Profit_PSP(*)
Profit_Bat_1(*)
Profit_Bat_2(*)

Generation(t,s,*) 
Charging(t,s,*)   
StoreLevel(t,s,*)
price_el(t,*)
;
scalar
x
;


loop(scen,

x = ord(scen)   ;
price(t) =  priceup(t,scen)$(ord(scen) eq x) ;

solve Storage_Profit using LP maximizing Profit
;

Profit_PSP(scen)      = sum(t, (G.l('PSP',t)-Charge.l('PSP',t))*real_price(t) ) ;
Profit_Bat_1(scen)    = sum(t, (G.l('Bat_1',t)-Charge.l('Bat_1',t))*real_price(t) ) ;
Profit_Bat_2(scen)    = sum(t, (G.l('Bat_2',t)-Charge.l('Bat_2',t))*real_price(t) ) ;

Generation(t,s,scen)   = G.l(s,t) ;
Charging(t,s,scen)     = Charge.l(s,t)    ;
StoreLevel(t,s,scen)   = SL.l(s,t)  ;

price_el(t,scen)    = price(t)  ; 

)


EXECUTE_UNLOAD '%output_dir%%result%.gdx'    

;

$onecho >out.tmp

         par=Profit_PSP                     rng=Profit!A3:B30      rdim=1 
         par=Profit_Bat_1                   rng=Profit!D3:E30      rdim=1 
         par=Profit_Bat_2                   rng=Profit!G3:H30      rdim=1 
         par=Generation                   rng=G!A1             rdim=1 cdim=2
         par=Charging                     rng=Charge!A1        rdim=1 cdim=2
         par=StoreLevel                   rng=SL!A1            rdim=1 cdim=2
         par=price_el                     rng=price!A1         rdim=1            

*         par=modelstats                    rng=stats!A2:B9900     rdim=1 cdim=0
*         par=solvestats                    rng=stats!D2:E9900     rdim=1 cdim=0

$offecho

execute "XLSTALK -c    %output_dir%%result%.xlsx" ;

EXECUTE 'gdxxrw %output_dir%%result%.gdx o=%output_dir%%result%.xlsx EpsOut=0 @out.tmp'
;

















