* 1.8V Two-Stage Miller OTA - final design netlist
.lib 'E:/analog_agent/ota_design_ai/.claude/skills/gmoverid-hspice/models/hspice/12sfe_spice_v1p2_rev0_usage.lib' tt_mos_varactor

.param VDD_VAL = 1.8
.param VCM_VAL = 0.9
.param VBP1_DROP = 0.600
.param VBP2_DROP = 0.528

* Device geometry
.param W_UM = 0.154
.param L_IN_UM = 0.18
.param L_LOAD_UM = 0.24
.param L_TAIL_UM = 0.24
.param L_STAGE2_UM = 0.24
.param L_P2_UM = 0.24

.param NFIN_IN = 20
.param NFIN_LOAD = 8
.param NFIN_TAIL = 12
.param NFIN_STAGE2 = 11
.param NFIN_P2 = 15

.param M_IN = 1
.param M_LOAD = 1
.param M_TAIL = 1
.param M_STAGE2 = 4
.param M_P2 = 4

* Compensation / load
.param CC_VAL = 3.5p
.param RZ_VAL = 6.8k
.param CL_VAL = 8p

* Supplies / bias
Vdd   vdd   0    DC VDD_VAL
Vinp  inp   0    DC VCM_VAL
Vinn  inn   0    DC VCM_VAL
Vbp1  vdd   vbp1 DC VBP1_DROP
Vbp2  vdd   vbp2 DC VBP2_DROP

* Stage 1: PMOS differential pair + NMOS mirror load
xm3 n1   n1   0    0   n18_ckt w='W_UM*1u' l='L_LOAD_UM*1u'   nfin=NFIN_LOAD   nf=1 m=M_LOAD
xm4 n2   n1   0    0   n18_ckt w='W_UM*1u' l='L_LOAD_UM*1u'   nfin=NFIN_LOAD   nf=1 m=M_LOAD
xm1 n1   inp  tail vdd p18_ckt w='W_UM*1u' l='L_IN_UM*1u'     nfin=NFIN_IN     nf=1 m=M_IN
xm2 n2   inn  tail vdd p18_ckt w='W_UM*1u' l='L_IN_UM*1u'     nfin=NFIN_IN     nf=1 m=M_IN
xm5 tail vbp1 vdd  vdd p18_ckt w='W_UM*1u' l='L_TAIL_UM*1u'   nfin=NFIN_TAIL   nf=1 m=M_TAIL

* Stage 2: NMOS common-source + PMOS current-source load
xm6 out  n2   0    0   n18_ckt w='W_UM*1u' l='L_STAGE2_UM*1u' nfin=NFIN_STAGE2 nf=1 m=M_STAGE2
xm7 out  vbp2 vdd  vdd p18_ckt w='W_UM*1u' l='L_P2_UM*1u'     nfin=NFIN_P2     nf=1 m=M_P2

* Miller compensation
Rz n2  rz  RZ_VAL
Cc rz  out CC_VAL

* Output load
Cl out 0 CL_VAL

.op
.end
