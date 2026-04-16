* 1.8V Two-Stage Miller OTA - final unity-follower transient netlist
.lib 'E:/analog_agent/ota_design_ai/.claude/skills/gmoverid-hspice/models/hspice/12sfe_spice_v1p2_rev0_usage.lib' tt_mos_varactor

.param VDD_VAL = 1.8
.param VBP1_DROP = 0.600
.param VBP2_DROP = 0.528

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

.param CC_VAL = 3.5p
.param RZ_VAL = 6.8k
.param CL_VAL = 8p

Vdd  vdd  0    DC VDD_VAL
Vbp1 vdd  vbp1 DC VBP1_DROP
Vbp2 vdd  vbp2 DC VBP2_DROP
Vinp inp  0    PULSE(0.75 1.05 10n 200p 200p 200n 500n)

* Stage 1
xm3 n1  n1  0    0   n18_ckt w='W_UM*1u' l='L_LOAD_UM*1u'   nfin=NFIN_LOAD   nf=1 m=M_LOAD
xm4 n2  n1  0    0   n18_ckt w='W_UM*1u' l='L_LOAD_UM*1u'   nfin=NFIN_LOAD   nf=1 m=M_LOAD
xm1 n1  out tail vdd p18_ckt w='W_UM*1u' l='L_IN_UM*1u'     nfin=NFIN_IN     nf=1 m=M_IN
xm2 n2  inp tail vdd p18_ckt w='W_UM*1u' l='L_IN_UM*1u'     nfin=NFIN_IN     nf=1 m=M_IN
xm5 tail vbp1 vdd  vdd p18_ckt w='W_UM*1u' l='L_TAIL_UM*1u' nfin=NFIN_TAIL   nf=1 m=M_TAIL

* Stage 2
xm6 out n2   0    0   n18_ckt w='W_UM*1u' l='L_STAGE2_UM*1u' nfin=NFIN_STAGE2 nf=1 m=M_STAGE2
xm7 out vbp2 vdd  vdd p18_ckt w='W_UM*1u' l='L_P2_UM*1u'     nfin=NFIN_P2     nf=1 m=M_P2

Rz n2 rz  RZ_VAL
Cc rz out CC_VAL
Cl out 0  CL_VAL

.tran 100p 500n
.print tran v(inp) v(out) v(n2)
.end
