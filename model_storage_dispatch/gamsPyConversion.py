from __future__ import annotations

import os
from pathlib import Path

import pandas as pd
import gamspy as gp
from gamspy import Sum, Ord, Problem, Sense


# ============================================================
# Paths matching the original GAMS file
# ============================================================

BASE_DIR = Path(
    "/Users/linukakoththigoda/Documents/GitHub/"
    "Bridging-ESM-with-an-ensemble-deep-learning-approach-for-EPF/"
    "model_storage_dispatch"
)

DATADIR = BASE_DIR / "data"
DATAIN = "InputData"

OUTPUT_DIR = BASE_DIR / "results"
RESULT = "Results_240713_gamspy"

INPUT_GDX = DATADIR / f"{DATAIN}.gdx"
OUTPUT_XLSX = OUTPUT_DIR / f"{RESULT}.xlsx"

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


# ============================================================
# Load symbols from existing InputData.gdx
# ============================================================

m = gp.Container(
    load_from=str(INPUT_GDX),
    working_directory=str(BASE_DIR / "gamspy_workdir"),
    debugging_level="keep_on_error",
)

# These are loaded from InputData.gdx, same as:
# $LOAD scen
# $LOAD map_TH
# $LOAD priceup
scen = m["scen"]
map_TH = m["map_TH"]
priceup = m["priceup"]


# ============================================================
# Sets
# ============================================================

s = gp.Set(
    m,
    name="s",
    description="storage",
    records=["PSP", "Bat_1", "Bat_2"],
)

t = gp.Set(
    m,
    name="t",
    description="time",
    records=[f"t{i}" for i in range(1, 17545)],
)

h = gp.Set(
    m,
    name="h",
    description="hour",
    records=[f"h{i}" for i in range(1, 25)],
)

tlast = gp.Set(m, name="tlast", domain=[t])
hlast = gp.Set(m, name="hlast", domain=[h])

tlast[t] = Ord(t) == gp.Card(t)
hlast[h] = Ord(h) == gp.Card(h)


# ============================================================
# Scalars / parameters
# ============================================================

cap = gp.Parameter(
    m,
    name="cap",
    description="turbine_pumping capacity",
    records=1.0,
)

price = gp.Parameter(
    m,
    name="price",
    domain=[t],
    description="wholesale electricity price [EUR per MWh]",
)

real_price = gp.Parameter(
    m,
    name="real_price",
    domain=[t],
    description="actual market price [EUR per MWh]",
)

eta = gp.Parameter(
    m,
    name="eta",
    domain=[s],
    description="efficiency of a storage cycle",
    records=pd.DataFrame(
        [
            ("PSP", 0.75),
            ("Bat_1", 0.80),
            ("Bat_2", 0.90),
        ],
        columns=["s", "value"],
    ),
)

ecr = gp.Parameter(
    m,
    name="ecr",
    domain=[s],
    description="energy capacity ratio",
    records=pd.DataFrame(
        [
            ("PSP", 7.0),
            ("Bat_1", 3.0),
            ("Bat_2", 1.0),
        ],
        columns=["s", "value"],
    ),
)

# real_price(t) = priceup(t,'Real Price');
real_price[t] = priceup[t, "Real Price"]


# ============================================================
# Variables
# ============================================================

Profit = gp.Variable(
    m,
    name="Profit",
    description="Profit of the storage unit [EUR]",
)

G = gp.Variable(
    m,
    name="G",
    domain=[s, t],
    type="Positive",
    description="electricity generation by storage [MWh per h]",
)

Charge = gp.Variable(
    m,
    name="Charge",
    domain=[s, t],
    type="Positive",
    description="charging storage electricity consumption [MWh per h]",
)

SL = gp.Variable(
    m,
    name="SL",
    domain=[s, t],
    type="Positive",
    description="Storage level [MWh]",
)


# ============================================================
# Equations
# ============================================================

Obj = gp.Equation(
    m,
    name="Obj",
    description="Objective Function maximizing profits",
)

StorageLevel = gp.Equation(
    m,
    name="StorageLevel",
    domain=[s, t, h],
    description="Storage level",
)

Store_Max = gp.Equation(
    m,
    name="Store_Max",
    domain=[s, t],
    description="maximum storage generation and charging [MWh per h]",
)

Gen_Max = gp.Equation(
    m,
    name="Gen_Max",
    domain=[s, t],
    description="generation is lower than storage level",
)

SL_Max = gp.Equation(
    m,
    name="SL_Max",
    domain=[s, t],
    description="maximum storage level",
)

SL_hfirst = gp.Equation(
    m,
    name="SL_hfirst",
    domain=[s, t],
)

SL_hlast = gp.Equation(
    m,
    name="SL_hlast",
    domain=[s, t],
)


# Obj..
# Profit =E= sum((s,t), (G(s,t)-Charge(s,t))*price(t));
Obj[...] = Profit == Sum((s, t), (G[s, t] - Charge[s, t]) * price[t])


# Store_Max(s,t)..
# G(s,t)+ Charge(s,t) =L= cap;
Store_Max[s, t] = G[s, t] + Charge[s, t] <= cap


# Gen_Max(s,t)..
# G(s,t) =L= SL(s,t-1);
#
# Important:
# In GAMS, for t1 the reference SL(s,t-1) has no predecessor,
# so the RHS effectively becomes 0. To preserve this behavior,
# define t1 separately and t2...t17544 with the lagged SL.
Gen_Max[s, t].where[Ord(t) == 1] = G[s, t] <= 0
Gen_Max[s, t].where[Ord(t) > 1] = G[s, t] <= SL[s, t - 1]


# SL_Max(s,t)..
# SL(s,t) =L= cap * ecr(s);
SL_Max[s, t] = SL[s, t] <= cap * ecr[s]


# StorageLevel(s,t,h)$(map_TH(t,h) and ord(h)>1)..
# SL(s,t) =E= SL(s,t-1) - G(s,t) + Charge(s,t)*eta(s);
StorageLevel[s, t, h].where[(map_TH[t, h]) & (Ord(h) > 1)] = (
    SL[s, t] == SL[s, t - 1] - G[s, t] + Charge[s, t] * eta[s]
)


# SL_hfirst(s,t)$map_TH(t,'h1')..
# SL(s,t) =E= 0* cap * ecr(s) + Charge(s,t)*eta(s) - G(s,t);
SL_hfirst[s, t].where[map_TH[t, "h1"]] = (
    SL[s, t] == Charge[s, t] * eta[s] - G[s, t]
)


# SL_hlast(s,t)$map_TH(t,'h24')..
# SL(s,t) =E= 0* cap * ecr(s);
SL_hlast[s, t].where[map_TH[t, "h24"]] = SL[s, t] == 0


# ============================================================
# Model Storage_Profit /all/
# ============================================================

Storage_Profit = gp.Model(
    m,
    name="Storage_Profit",
    equations=[
        Obj,
        StorageLevel,
        Store_Max,
        Gen_Max,
        SL_Max,
        SL_hfirst,
        SL_hlast,
    ],
    problem=Problem.LP,
    sense=Sense.MAX,
    objective=Profit,
)


# ============================================================
# Output containers, equivalent to GAMS Parameters
# ============================================================

profit_psp_records = []
profit_bat_1_records = []
profit_bat_2_records = []

generation_records = []
charging_records = []
storelevel_records = []
price_el_records = []


# Helper: robustly extract one-dimensional parameter as Series
def parameter_to_series(param: gp.Parameter, index_col: str) -> pd.Series:
    rec = param.records.copy()
    return rec.set_index(index_col)["value"]


# Helper: robustly extract variable levels
def variable_level_records(var: gp.Variable) -> pd.DataFrame:
    rec = var.records.copy()
    if "level" not in rec.columns:
        raise RuntimeError(
            f"Expected GAMSPy variable records for {var.name} to contain a 'level' column. "
            f"Columns found: {list(rec.columns)}"
        )
    return rec


real_price_series = parameter_to_series(real_price, "t")


# ============================================================
# loop(scen, ...)
# ============================================================

scenario_names = scen.records["uni"].tolist()

for scen_name in scenario_names:
    print(f"Solving scenario: {scen_name}")

    # x = ord(scen);
    # price(t) = priceup(t,scen)$(ord(scen) eq x);
    #
    # In the loop body, this is equivalent to assigning the current
    # scenario column of priceup to price.
    price[t] = priceup[t, scen_name]

    # solve Storage_Profit using LP maximizing Profit;
    Storage_Profit.solve()

    G_rec = variable_level_records(G)
    Charge_rec = variable_level_records(Charge)
    SL_rec = variable_level_records(SL)

    # Same as:
    # Profit_PSP(scen) = sum(t, (G.l('PSP',t)-Charge.l('PSP',t))*real_price(t));
    G_wide = G_rec.pivot(index="t", columns="s", values="level")
    Charge_wide = Charge_rec.pivot(index="t", columns="s", values="level")

    profit_psp = ((G_wide["PSP"] - Charge_wide["PSP"]) * real_price_series).sum()
    profit_bat_1 = ((G_wide["Bat_1"] - Charge_wide["Bat_1"]) * real_price_series).sum()
    profit_bat_2 = ((G_wide["Bat_2"] - Charge_wide["Bat_2"]) * real_price_series).sum()

    profit_psp_records.append((scen_name, float(profit_psp)))
    profit_bat_1_records.append((scen_name, float(profit_bat_1)))
    profit_bat_2_records.append((scen_name, float(profit_bat_2)))

    # Generation(t,s,scen) = G.l(s,t);
    for _, row in G_rec.iterrows():
        generation_records.append(
            (row["t"], row["s"], scen_name, float(row["level"]))
        )

    # Charging(t,s,scen) = Charge.l(s,t);
    for _, row in Charge_rec.iterrows():
        charging_records.append(
            (row["t"], row["s"], scen_name, float(row["level"]))
        )

    # StoreLevel(t,s,scen) = SL.l(s,t);
    for _, row in SL_rec.iterrows():
        storelevel_records.append(
            (row["t"], row["s"], scen_name, float(row["level"]))
        )

    # price_el(t,scen) = price(t);
    price_rec = price.records.copy()
    for _, row in price_rec.iterrows():
        price_el_records.append(
            (row["t"], scen_name, float(row["value"]))
        )


# ============================================================
# Write equivalent Excel output
# ============================================================
# ============================================================
# Convert long records to DataFrames
# ============================================================

profit_psp_df = pd.DataFrame(
    profit_psp_records,
    columns=["scenario", "Profit_PSP"],
)

profit_bat_1_df = pd.DataFrame(
    profit_bat_1_records,
    columns=["scenario", "Profit_Bat_1"],
)

profit_bat_2_df = pd.DataFrame(
    profit_bat_2_records,
    columns=["scenario", "Profit_Bat_2"],
)

generation_df = pd.DataFrame(
    generation_records,
    columns=["t", "s", "scenario", "Generation"],
)

charging_df = pd.DataFrame(
    charging_records,
    columns=["t", "s", "scenario", "Charging"],
)

storelevel_df = pd.DataFrame(
    storelevel_records,
    columns=["t", "s", "scenario", "StoreLevel"],
)

price_el_df = pd.DataFrame(
    price_el_records,
    columns=["t", "scenario", "price_el"],
)


# ============================================================
# Reshape to match GAMS/GDXXRW-style output
# Original GAMS used:
# Generation(t,s,*) with rdim=1 cdim=2
# Therefore:
# rows    = t
# columns = s × scenario
# ============================================================

generation_wide = generation_df.pivot_table(
    index="t",
    columns=["s", "scenario"],
    values="Generation",
    aggfunc="first",
)

charging_wide = charging_df.pivot_table(
    index="t",
    columns=["s", "scenario"],
    values="Charging",
    aggfunc="first",
)

storelevel_wide = storelevel_df.pivot_table(
    index="t",
    columns=["s", "scenario"],
    values="StoreLevel",
    aggfunc="first",
)

price_wide = price_el_df.pivot_table(
    index="t",
    columns="scenario",
    values="price_el",
    aggfunc="first",
)


# Make sure time is sorted as t1, t2, ..., t17544
def sort_t_index(df):
    return df.loc[
        sorted(df.index, key=lambda x: int(str(x).replace("t", "")))
    ]


generation_wide = sort_t_index(generation_wide)
charging_wide = sort_t_index(charging_wide)
storelevel_wide = sort_t_index(storelevel_wide)
price_wide = sort_t_index(price_wide)


# ============================================================
# Write Excel output
# ============================================================

with pd.ExcelWriter(OUTPUT_XLSX, engine="openpyxl") as writer:
    # Profit sheet, similar to original GAMS ranges
    profit_psp_df.to_excel(
        writer,
        sheet_name="Profit",
        index=False,
        startrow=2,
        startcol=0,
    )

    profit_bat_1_df.to_excel(
        writer,
        sheet_name="Profit",
        index=False,
        startrow=2,
        startcol=3,
    )

    profit_bat_2_df.to_excel(
        writer,
        sheet_name="Profit",
        index=False,
        startrow=2,
        startcol=6,
    )

    # Wide-format sheets, matching rdim=1 cdim=2 logic
    generation_wide.to_excel(writer, sheet_name="G")
    charging_wide.to_excel(writer, sheet_name="Charge")
    storelevel_wide.to_excel(writer, sheet_name="SL")
    price_wide.to_excel(writer, sheet_name="price")

print(f"Saved results to: {OUTPUT_XLSX}")