# Ultracs BASIC Extract File Inventory

Scanned **153 BASIC/BASIC-like programs** using the content-signature rule documented in [repo_profile_ultracs.md](repo_profile_ultracs.md). This table lists detected output files written through `KBDOSOUTPUT*` or sequential paths opened with `OPENSEQ`; ordinary writes to MultiValue business files are excluded.

Format is reported as pipe-delimited only when source shows a pipe separator used in output-record assembly. Fixed-width is a candidate only where width-formatting syntax is found; otherwise the format is marked not determined. Dynamic path expressions are preserved as written.

| source_program | output_file_or_path | format | write_form |
|---|---|---|---|---|
| [DATAMASK](../../kb-ultracs-datawarehouse/DATAMASK) | &COMO&/datamask.log | Other / format not determined (no delimiter or fixed-width evidence tied to this output) | WRITESEQ |
| [KWCC_B2KCUST](../../kb-ultracs-datawarehouse/KWCC_B2KCUST) | KBCC.OUTFILE/CCB2KLOG.TXT | Pipe-delimited (SEP is assigned '\|'; this written payload uses :SEP:) | WRITESEQ |
| [KWCC_B2KCUST](../../kb-ultracs-datawarehouse/KWCC_B2KCUST) | KBDOSOUTPUT/DWLOG.TXT | Other / format not determined (no delimiter or fixed-width evidence tied to this output) | WRITE |
| [KWCC_REJECTS](../../kb-ultracs-datawarehouse/KWCC_REJECTS) | KBCC.OUTFILE/DESREJECTS.TXT | Fixed-width candidate (fixed-width substring/formatting syntax is present in the written payload) | WRITESEQ |
| [KWCC_REJECTS](../../kb-ultracs-datawarehouse/KWCC_REJECTS) | KBDOSOUTPUT/DWLOG.TXT | Other / format not determined (no delimiter or fixed-width evidence tied to this output) | WRITE |
| [KWDD_REJECTS](../../kb-ultracs-datawarehouse/KWDD_REJECTS) | KBDOSOUTPUT/DWLOG.TXT | Other / format not determined (no delimiter or fixed-width evidence tied to this output) | WRITE |
| [KWDD_REJECTS](../../kb-ultracs-datawarehouse/KWDD_REJECTS) | KBDOSOUTPUT/DWREJECTS.TXT | Pipe-delimited (SEP is assigned '\|'; this written payload uses :SEP:) | WRITE; WRITESEQ |
| [KWDW_ACC](../../kb-ultracs-datawarehouse/KWDW_ACC) | KBDOSOUTPUT/CONTROL_CL.TXT | Other / format not determined (no delimiter or fixed-width evidence tied to this output) | WRITE |
| [KWDW_ACC](../../kb-ultracs-datawarehouse/KWDW_ACC) | KBDOSOUTPUT/CONTROLBAL.TXT | Other / format not determined (no delimiter or fixed-width evidence tied to this output) | WRITE |
| [KWDW_ACC](../../kb-ultracs-datawarehouse/KWDW_ACC) | KBDOSOUTPUT/DWACC{HEAD} | Pipe-delimited (SEP is assigned '\|'; this written payload uses :SEP:) | WRITE; WRITESEQ |
| [KWDW_ACC](../../kb-ultracs-datawarehouse/KWDW_ACC) | KBDOSOUTPUT/DWDBUST.TXT | Pipe-delimited (SEP is assigned '\|'; this written payload uses :SEP:) | WRITE; WRITESEQ |
| [KWDW_ACC](../../kb-ultracs-datawarehouse/KWDW_ACC) | KBDOSOUTPUT/DWLOG.TXT | Pipe-delimited (SEP is assigned '\|'; this written payload uses :SEP:) | WRITE |
| [KWDW_ACC](../../kb-ultracs-datawarehouse/KWDW_ACC) | KBDOSOUTPUT/DWREL{HEAD} | Pipe-delimited (SEP is assigned '\|'; this written payload uses :SEP:) | WRITE; WRITESEQ |
| [KWDW_ACC](../../kb-ultracs-datawarehouse/KWDW_ACC) | KBDOSOUTPUT/DWREP.TXT | Pipe-delimited (SEP is assigned '\|'; this written payload uses :SEP:) | WRITE; WRITESEQ |
| [KWDW_ACC](../../kb-ultracs-datawarehouse/KWDW_ACC) | KBDOSOUTPUT/DWSAVBR.TXT | Pipe-delimited (SEP is assigned '\|'; this written payload uses :SEP:) | WRITE; WRITESEQ |
| [KWDW_ACC](../../kb-ultracs-datawarehouse/KWDW_ACC) | KBDOSOUTPUT/DWTDS.TXT | Pipe-delimited (SEP is assigned '\|'; this written payload uses :SEP:) | WRITE; WRITESEQ |
| [KWDW_ACC](../../kb-ultracs-datawarehouse/KWDW_ACC) | KBDOSOUTPUT/DWUNCLD.TXT | Pipe-delimited (SEP is assigned '\|'; this written payload uses :SEP:) | WRITE; WRITESEQ |
| [KWDW_ACC](../../kb-ultracs-datawarehouse/KWDW_ACC) | KBDOSOUTPUT/TCONTROL.TXT | Other / format not determined (no delimiter or fixed-width evidence tied to this output) | WRITEV |
| [KWDW_ACC](../../kb-ultracs-datawarehouse/KWDW_ACC) | KBDOSOUTPUT/YCONTROL1.TXT | Other / format not determined (no delimiter or fixed-width evidence tied to this output) | WRITE |
| [KWDW_ACC](../../kb-ultracs-datawarehouse/KWDW_ACC) | KBDOSOUTPUT3/CNTRLP_FIN.TXT | Other / format not determined (no delimiter or fixed-width evidence tied to this output) | WRITE |
| [KWDW_ACC2](../../kb-ultracs-datawarehouse/KWDW_ACC2) | KBDOSOUTPUT/DWACFEE.TXT | Pipe-delimited (SEP is assigned '\|'; this written payload uses :SEP:) | WRITE; WRITESEQ |
| [KWDW_ACC2](../../kb-ultracs-datawarehouse/KWDW_ACC2) | KBDOSOUTPUT/DWLOG.TXT | Other / format not determined (no delimiter or fixed-width evidence tied to this output) | WRITE |
| [KWDW_ACC2_AUTO](../../kb-ultracs-datawarehouse/KWDW_ACC2_AUTO) | KBDOSOUTPUT/DWDBUST.TXT | Pipe-delimited (SEP is assigned '\|'; this written payload uses :SEP:) | WRITE; WRITESEQ |
| [KWDW_ACC2_AUTO](../../kb-ultracs-datawarehouse/KWDW_ACC2_AUTO) | KBDOSOUTPUT/DWLOG.TXT | Other / format not determined (no delimiter or fixed-width evidence tied to this output) | WRITE |
| [KWDW_ACC2_AUTO](../../kb-ultracs-datawarehouse/KWDW_ACC2_AUTO) | KBDOSOUTPUT/DWREL{HEAD} | Pipe-delimited (SEP is assigned '\|'; this written payload uses :SEP:) | WRITE; WRITESEQ |
| [KWDW_ACC2_AUTO](../../kb-ultracs-datawarehouse/KWDW_ACC2_AUTO) | KBDOSOUTPUT/DWREP.TXT | Pipe-delimited (SEP is assigned '\|'; this written payload uses :SEP:) | WRITE; WRITESEQ |
| [KWDW_ACC2_AUTO](../../kb-ultracs-datawarehouse/KWDW_ACC2_AUTO) | KBDOSOUTPUT/DWSAVBR.TXT | Pipe-delimited (SEP is assigned '\|'; this written payload uses :SEP:) | WRITE; WRITESEQ |
| [KWDW_ACC2_AUTO](../../kb-ultracs-datawarehouse/KWDW_ACC2_AUTO) | KBDOSOUTPUT/DWUNCLD.TXT | Pipe-delimited (SEP is assigned '\|'; this written payload uses :SEP:) | WRITE; WRITESEQ |
| [KWDW_ACC_AUTO](../../kb-ultracs-datawarehouse/KWDW_ACC_AUTO) | KBDOSOUTPUT/CONTROL_CL.TXT | Other / format not determined (no delimiter or fixed-width evidence tied to this output) | WRITE |
| [KWDW_ACC_AUTO](../../kb-ultracs-datawarehouse/KWDW_ACC_AUTO) | KBDOSOUTPUT/CONTROLBAL.TXT | Other / format not determined (no delimiter or fixed-width evidence tied to this output) | WRITE |
| [KWDW_ACC_AUTO](../../kb-ultracs-datawarehouse/KWDW_ACC_AUTO) | KBDOSOUTPUT/DWACC{HEAD} | Pipe-delimited (SEP is assigned '\|'; this written payload uses :SEP:) | WRITE; WRITESEQ |
| [KWDW_ACC_AUTO](../../kb-ultracs-datawarehouse/KWDW_ACC_AUTO) | KBDOSOUTPUT/DWLOG.TXT | Other / format not determined (no delimiter or fixed-width evidence tied to this output) | WRITE |
| [KWDW_ACC_AUTO](../../kb-ultracs-datawarehouse/KWDW_ACC_AUTO) | KBDOSOUTPUT/TCONTROL.TXT | Other / format not determined (no delimiter or fixed-width evidence tied to this output) | WRITEV |
| [KWDW_ACC_AUTO](../../kb-ultracs-datawarehouse/KWDW_ACC_AUTO) | KBDOSOUTPUT/YCONTROL1.TXT | Other / format not determined (no delimiter or fixed-width evidence tied to this output) | WRITE |
| [KWDW_ACC_AUTO](../../kb-ultracs-datawarehouse/KWDW_ACC_AUTO) | KBDOSOUTPUT3/CNTRLP_FIN.TXT | Other / format not determined (no delimiter or fixed-width evidence tied to this output) | WRITE |
| [KWDW_ACC_ORIG](../../kb-ultracs-datawarehouse/KWDW_ACC_ORIG) | KBDOSOUTPUT/CONTROL_CL.TXT | Other / format not determined (no delimiter or fixed-width evidence tied to this output) | WRITE |
| [KWDW_ACC_ORIG](../../kb-ultracs-datawarehouse/KWDW_ACC_ORIG) | KBDOSOUTPUT/CONTROL_CL2.TXT | Other / format not determined (no delimiter or fixed-width evidence tied to this output) | WRITE |
| [KWDW_ACC_ORIG](../../kb-ultracs-datawarehouse/KWDW_ACC_ORIG) | KBDOSOUTPUT/CONTROLBAL.TXT | Other / format not determined (no delimiter or fixed-width evidence tied to this output) | WRITE |
| [KWDW_ACC_ORIG](../../kb-ultracs-datawarehouse/KWDW_ACC_ORIG) | KBDOSOUTPUT/DWACC{HEAD} | Pipe-delimited (SEP is assigned '\|'; this written payload uses :SEP:) | WRITE; WRITESEQ |
| [KWDW_ACC_ORIG](../../kb-ultracs-datawarehouse/KWDW_ACC_ORIG) | KBDOSOUTPUT/DWEOD.TXT | Pipe-delimited (SEP is assigned '\|'; this written payload uses :SEP:) | WRITE; WRITESEQ |
| [KWDW_ACC_ORIG](../../kb-ultracs-datawarehouse/KWDW_ACC_ORIG) | KBDOSOUTPUT/DWISUMM.TXT | Pipe-delimited (SEP is assigned '\|'; this written payload uses :SEP:) | WRITE; WRITESEQ |
| [KWDW_ACC_ORIG](../../kb-ultracs-datawarehouse/KWDW_ACC_ORIG) | KBDOSOUTPUT/DWLOG.TXT | Pipe-delimited (SEP is assigned '\|'; this written payload uses :SEP:) | WRITE |
| [KWDW_ACC_ORIG](../../kb-ultracs-datawarehouse/KWDW_ACC_ORIG) | KBDOSOUTPUT/DWREL{HEAD} | Pipe-delimited (SEP is assigned '\|'; this written payload uses :SEP:) | WRITE; WRITESEQ |
| [KWDW_ACC_ORIG](../../kb-ultracs-datawarehouse/KWDW_ACC_ORIG) | KBDOSOUTPUT/DWREP.TXT | Pipe-delimited (SEP is assigned '\|'; this written payload uses :SEP:) | WRITE; WRITESEQ |
| [KWDW_ACC_ORIG](../../kb-ultracs-datawarehouse/KWDW_ACC_ORIG) | KBDOSOUTPUT/DWSAVBR.TXT | Pipe-delimited (SEP is assigned '\|'; this written payload uses :SEP:) | WRITE; WRITESEQ |
| [KWDW_ACC_ORIG](../../kb-ultracs-datawarehouse/KWDW_ACC_ORIG) | KBDOSOUTPUT/DWTDS.TXT | Pipe-delimited (SEP is assigned '\|'; this written payload uses :SEP:) | WRITE; WRITESEQ |
| [KWDW_ACC_ORIG](../../kb-ultracs-datawarehouse/KWDW_ACC_ORIG) | KBDOSOUTPUT/DWUNCLD.TXT | Pipe-delimited (SEP is assigned '\|'; this written payload uses :SEP:) | WRITE; WRITESEQ |
| [KWDW_ACC_ORIG](../../kb-ultracs-datawarehouse/KWDW_ACC_ORIG) | KBDOSOUTPUT/TCONTROL.TXT | Other / format not determined (no delimiter or fixed-width evidence tied to this output) | WRITEV |
| [KWDW_ACC_ORIG](../../kb-ultracs-datawarehouse/KWDW_ACC_ORIG) | KBDOSOUTPUT/ZCONTROL1.TXT | Other / format not determined (no delimiter or fixed-width evidence tied to this output) | WRITE |
| [KWDW_ACCBAL](../../kb-ultracs-datawarehouse/KWDW_ACCBAL) | KBDOSOUTPUT/ACCBAL.TXT | Pipe-delimited (SEP is assigned '\|'; this written payload uses :SEP:) | WRITE; WRITESEQ |
| [KWDW_ACCBALREL](../../kb-ultracs-datawarehouse/KWDW_ACCBALREL) | KBDOSOUTPUT/ACCBAL.TXT | Pipe-delimited (SEP is assigned '\|'; this written payload uses :SEP:) | WRITE; WRITESEQ |
| [KWDW_ACCBALREL](../../kb-ultracs-datawarehouse/KWDW_ACCBALREL) | KBDOSOUTPUT/ACCREL.TXT | Pipe-delimited (SEP is assigned '\|'; this written payload uses :SEP:) | WRITE; WRITESEQ |
| [KWDW_ACCREC](../../kb-ultracs-datawarehouse/KWDW_ACCREC) | KBDOSOUTPUT/ACCREC_{BHEAD} | Pipe-delimited (SEP is assigned '\|'; this written payload uses :SEP:) | WRITE; WRITESEQ |
| [KWDW_ACCREC](../../kb-ultracs-datawarehouse/KWDW_ACCREC) | KBDOSOUTPUT/DWLOG.TXT | Other / format not determined (no delimiter or fixed-width evidence tied to this output) | WRITE |
| [KWDW_ACCREL](../../kb-ultracs-datawarehouse/KWDW_ACCREL) | KBDOSOUTPUT/ACCBAL.TXT | Pipe-delimited (SEP is assigned '\|'; this written payload uses :SEP:) | WRITE; WRITESEQ |
| [KWDW_ACCREL](../../kb-ultracs-datawarehouse/KWDW_ACCREL) | KBDOSOUTPUT/ACCREL.TXT | Pipe-delimited (SEP is assigned '\|'; this written payload uses :SEP:) | WRITE; WRITESEQ |
| [KWDW_ACCX](../../kb-ultracs-datawarehouse/KWDW_ACCX) | KBDOSOUTPUT/DWACC{HEAD} | Pipe-delimited (SEP is assigned '\|'; this written payload uses :SEP:) | WRITE; WRITESEQ |
| [KWDW_ACCX](../../kb-ultracs-datawarehouse/KWDW_ACCX) | KBDOSOUTPUT/DWLOG.TXT | Pipe-delimited (SEP is assigned '\|'; this written payload uses :SEP:) | WRITE |
| [KWDW_ACCX](../../kb-ultracs-datawarehouse/KWDW_ACCX) | KBDOSOUTPUT/DWREL{HEAD} | Pipe-delimited (SEP is assigned '\|'; this written payload uses :SEP:) | WRITE; WRITESEQ |
| [KWDW_ACCX](../../kb-ultracs-datawarehouse/KWDW_ACCX) | KBDOSOUTPUT/DWREP.TXT | Pipe-delimited (SEP is assigned '\|'; this written payload uses :SEP:) | WRITE; WRITESEQ |
| [KWDW_ACCX](../../kb-ultracs-datawarehouse/KWDW_ACCX) | KBDOSOUTPUT/DWTDS.TXT | Pipe-delimited (SEP is assigned '\|'; this written payload uses :SEP:) | WRITE; WRITESEQ |
| [KWDW_ACCX](../../kb-ultracs-datawarehouse/KWDW_ACCX) | KBDOSOUTPUT/DWUNCLD.TXT | Pipe-delimited (SEP is assigned '\|'; this written payload uses :SEP:) | WRITE; WRITESEQ |
| [KWDW_ACCX](../../kb-ultracs-datawarehouse/KWDW_ACCX) | KBDOSOUTPUT/ZCONTROL1.TXT | Other / format not determined (no delimiter or fixed-width evidence tied to this output) | WRITE |
| [KWDW_ACFEE](../../kb-ultracs-datawarehouse/KWDW_ACFEE) | KBDOSOUTPUT/DWACFEE.TXT | Other / format not determined (no delimiter or fixed-width evidence tied to this output) | WRITE |
| [KWDW_ACFEE](../../kb-ultracs-datawarehouse/KWDW_ACFEE) | KBDOSOUTPUT/DWDDFEE.TXT | Other / format not determined (no delimiter or fixed-width evidence tied to this output) | WRITE; WRITESEQ |
| [KWDW_ACFEE](../../kb-ultracs-datawarehouse/KWDW_ACFEE) | KBDOSOUTPUT/DWFEECDS.TXT | Other / format not determined (no delimiter or fixed-width evidence tied to this output) | WRITE |
| [KWDW_ACFEE](../../kb-ultracs-datawarehouse/KWDW_ACFEE) | KBDOSOUTPUT/DWFEEDIS.TXT | Other / format not determined (no delimiter or fixed-width evidence tied to this output) | WRITE |
| [KWDW_ACFEE](../../kb-ultracs-datawarehouse/KWDW_ACFEE) | KBDOSOUTPUT/DWFWAIVER.TXT | Pipe-delimited (SEP is assigned '\|'; this written payload uses :SEP:) | WRITE; WRITESEQ |
| [KWDW_ACFEE](../../kb-ultracs-datawarehouse/KWDW_ACFEE) | KBDOSOUTPUT/DWLOG.TXT | Other / format not determined (no delimiter or fixed-width evidence tied to this output) | WRITE |
| [KWDW_AGENCY](../../kb-ultracs-datawarehouse/KWDW_AGENCY) | KBDOSOUTPUT/DWAGENCY.TXT | Other / format not determined (no delimiter or fixed-width evidence tied to this output) | WRITE |
| [KWDW_AGENCY](../../kb-ultracs-datawarehouse/KWDW_AGENCY) | KBDOSOUTPUT/DWLOG.TXT | Other / format not determined (no delimiter or fixed-width evidence tied to this output) | WRITE |
| [KWDW_AML1](../../kb-ultracs-datawarehouse/KWDW_AML1) | KBDOSOUTPUT3/AMLACC.TXT | Pipe-delimited (SEP is assigned '\|'; this written payload uses :SEP:) | WRITE; WRITESEQ |
| [KWDW_AML1](../../kb-ultracs-datawarehouse/KWDW_AML1) | KBDOSOUTPUT3/AMLREL.TXT | Pipe-delimited (SEP is assigned '\|'; this written payload uses :SEP:) | WRITE; WRITESEQ |
| [KWDW_AML2](../../kb-ultracs-datawarehouse/KWDW_AML2) | KBDOSOUTPUT/AMLBUSCL.TXT | Other / format not determined (no delimiter or fixed-width evidence tied to this output) | WRITE |
| [KWDW_AML2](../../kb-ultracs-datawarehouse/KWDW_AML2) | KBDOSOUTPUT/AMLBUSLINKS.TXT | Other / format not determined (no delimiter or fixed-width evidence tied to this output) | WRITE |
| [KWDW_AML2](../../kb-ultracs-datawarehouse/KWDW_AML2) | KBDOSOUTPUT/AMLBUSREL.TXT | Other / format not determined (no delimiter or fixed-width evidence tied to this output) | WRITE |
| [KWDW_AML2](../../kb-ultracs-datawarehouse/KWDW_AML2) | KBDOSOUTPUT/AMLCLOG.TXT | Other / format not determined (no delimiter or fixed-width evidence tied to this output) | WRITE |
| [KWDW_AML2](../../kb-ultracs-datawarehouse/KWDW_AML2) | KBDOSOUTPUT/AMLCLUPD.TXT | Other / format not determined (no delimiter or fixed-width evidence tied to this output) | WRITE |
| [KWDW_AML2](../../kb-ultracs-datawarehouse/KWDW_AML2) | KBDOSOUTPUT3/AMLBUSCL.TXT | Pipe-delimited (SEP is assigned '\|'; this written payload uses :SEP:) | WRITESEQ |
| [KWDW_AML2](../../kb-ultracs-datawarehouse/KWDW_AML2) | KBDOSOUTPUT3/AMLBUSLINKS.TXT | Pipe-delimited (SEP is assigned '\|'; this written payload uses :SEP:) | WRITESEQ |
| [KWDW_AML2](../../kb-ultracs-datawarehouse/KWDW_AML2) | KBDOSOUTPUT3/AMLBUSREL.TXT | Pipe-delimited (SEP is assigned '\|'; this written payload uses :SEP:) | WRITESEQ |
| [KWDW_AML2](../../kb-ultracs-datawarehouse/KWDW_AML2) | KBDOSOUTPUT3/AMLCLUPD.TXT | Pipe-delimited (SEP is assigned '\|'; this written payload uses :SEP:) | WRITESEQ |
| [KWDW_AML3](../../kb-ultracs-datawarehouse/KWDW_AML3) | KBDOSOUTPUT/AMLKBID.TXT | Other / format not determined (no delimiter or fixed-width evidence tied to this output) | WRITE |
| [KWDW_AML3](../../kb-ultracs-datawarehouse/KWDW_AML3) | KBDOSOUTPUT/AMLKBID2.TXT | Other / format not determined (no delimiter or fixed-width evidence tied to this output) | WRITE |
| [KWDW_AML3](../../kb-ultracs-datawarehouse/KWDW_AML3) | KBDOSOUTPUT3/AMLKBID.TXT | Pipe-delimited (SEP is assigned '\|'; this written payload uses :SEP:) | WRITESEQ |
| [KWDW_AML3](../../kb-ultracs-datawarehouse/KWDW_AML3) | KBDOSOUTPUT3/AMLKBID2.TXT | Pipe-delimited (SEP is assigned '\|'; this written payload uses :SEP:) | WRITESEQ |
| [KWDW_AMLRUN](../../kb-ultracs-datawarehouse/KWDW_AMLRUN) | KBDOSOUTPUT3/AML_CONTROL.TXT | Other / format not determined (no delimiter or fixed-width evidence tied to this output) | WRITE |
| [KWDW_AMORT](../../kb-ultracs-datawarehouse/KWDW_AMORT) | KBDOSOUTPUT/AMORTCONTROL.TXT | Other / format not determined (no delimiter or fixed-width evidence tied to this output) | WRITE |
| [KWDW_AMORT](../../kb-ultracs-datawarehouse/KWDW_AMORT) | KBDOSOUTPUT/CTRL_AMORT.TXT | Other / format not determined (no delimiter or fixed-width evidence tied to this output) | WRITE |
| [KWDW_AMORT](../../kb-ultracs-datawarehouse/KWDW_AMORT) | KBDOSOUTPUT/DWKWAMORT.TXT | Pipe-delimited (SEP is assigned '\|'; this written payload uses :SEP:) | WRITE; WRITESEQ |
| [KWDW_AMORT](../../kb-ultracs-datawarehouse/KWDW_AMORT) | KBDOSOUTPUT/DWLOG.TXT | Other / format not determined (no delimiter or fixed-width evidence tied to this output) | WRITE |
| [KWDW_APPROVALS](../../kb-ultracs-datawarehouse/KWDW_APPROVALS) | KBDOSOUTPUT/DWLNAPP.TXT | Pipe-delimited (SEP is assigned '\|'; this written payload uses :SEP:) | WRITE; WRITESEQ |
| [KWDW_APPROVALS](../../kb-ultracs-datawarehouse/KWDW_APPROVALS) | KBDOSOUTPUT/DWLOG.TXT | Other / format not determined (no delimiter or fixed-width evidence tied to this output) | WRITE |
| [KWDW_APPROVALS](../../kb-ultracs-datawarehouse/KWDW_APPROVALS) | KBDOSOUTPUT2/DWLNDISB.TXT | Pipe-delimited (SEP is assigned '\|'; this written payload uses :SEP:) | WRITE; WRITESEQ |
| [KWDW_APS](../../kb-ultracs-datawarehouse/KWDW_APS) | KBDOSOUTPUT/DWAFFP.TXT | Pipe-delimited (SEP is assigned '\|'; this written payload uses :SEP:) | WRITE; WRITESEQ |
| [KWDW_ARREARS](../../kb-ultracs-datawarehouse/KWDW_ARREARS) | KBDOSOUTPUT/DWKWARR.TXT | Other / format not determined (no delimiter or fixed-width evidence tied to this output) | WRITE |
| [KWDW_ARREARS](../../kb-ultracs-datawarehouse/KWDW_ARREARS) | KBDOSOUTPUT/DWLOG.TXT | Other / format not determined (no delimiter or fixed-width evidence tied to this output) | WRITE |
| [KWDW_ATM](../../kb-ultracs-datawarehouse/KWDW_ATM) | KBDOSOUTPUT/DWLOG.TXT | Other / format not determined (no delimiter or fixed-width evidence tied to this output) | WRITE |
| [KWDW_ATM](../../kb-ultracs-datawarehouse/KWDW_ATM) | KBDOSOUTPUT2/DWATMLOC.TXT | Pipe-delimited (SEP is assigned '\|'; this written payload uses :SEP:) | WRITE; WRITESEQ |
| [KWDW_ATM](../../kb-ultracs-datawarehouse/KWDW_ATM) | KBDOSOUTPUT2/DWATMREQ.TXT | Pipe-delimited (SEP is assigned '\|'; this written payload uses :SEP:) | WRITE; WRITESEQ |
| [KWDW_ATM](../../kb-ultracs-datawarehouse/KWDW_ATM) | KBDOSOUTPUT2/DWATMWVR.TXT | Pipe-delimited (SEP is assigned '\|'; this written payload uses :SEP:) | WRITE; WRITESEQ |
| [KWDW_ATM](../../kb-ultracs-datawarehouse/KWDW_ATM) | KBDOSOUTPUT2/DWBRCARD.TXT | Pipe-delimited (SEP is assigned '\|'; this written payload uses :SEP:) | WRITE; WRITESEQ |
| [KWDW_ATM](../../kb-ultracs-datawarehouse/KWDW_ATM) | KBDOSOUTPUT2/DWBRCDET.TXT | Pipe-delimited (SEP is assigned '\|'; this written payload uses :SEP:) | WRITE; WRITESEQ |
| [KWDW_ATM](../../kb-ultracs-datawarehouse/KWDW_ATM) | KBDOSOUTPUT2/DWBRDEBC.TXT | Other / format not determined (no delimiter or fixed-width evidence tied to this output) | WRITE |
| [KWDW_ATM](../../kb-ultracs-datawarehouse/KWDW_ATM) | KBDOSOUTPUT2/DWCARDLK.TXT | Other / format not determined (no delimiter or fixed-width evidence tied to this output) | WRITE |
| [KWDW_ATM](../../kb-ultracs-datawarehouse/KWDW_ATM) | KBDOSOUTPUT2/DWCARDS.TXT | Pipe-delimited (SEP is assigned '\|'; this written payload uses :SEP:) | WRITE; WRITESEQ |
| [KWDW_ATM_TOKEN](../../kb-ultracs-datawarehouse/KWDW_ATM_TOKEN) | KBDOSOUTPUT/DWLOG.TXT | Other / format not determined (no delimiter or fixed-width evidence tied to this output) | WRITE |
| [KWDW_ATM_TOKEN](../../kb-ultracs-datawarehouse/KWDW_ATM_TOKEN) | KBDOSOUTPUT2/DWATMLOC.TXT | Pipe-delimited (SEP is assigned '\|'; this written payload uses :SEP:) | WRITE; WRITESEQ |
| [KWDW_ATM_TOKEN](../../kb-ultracs-datawarehouse/KWDW_ATM_TOKEN) | KBDOSOUTPUT2/DWATMREQ.TXT | Pipe-delimited (SEP is assigned '\|'; this written payload uses :SEP:) | WRITE; WRITESEQ |
| [KWDW_ATM_TOKEN](../../kb-ultracs-datawarehouse/KWDW_ATM_TOKEN) | KBDOSOUTPUT2/DWATMWVR.TXT | Pipe-delimited (SEP is assigned '\|'; this written payload uses :SEP:) | WRITE; WRITESEQ |
| [KWDW_ATM_TOKEN](../../kb-ultracs-datawarehouse/KWDW_ATM_TOKEN) | KBDOSOUTPUT2/DWBRCARD.TXT | Pipe-delimited (SEP is assigned '\|'; this written payload uses :SEP:) | WRITE; WRITESEQ |
| [KWDW_ATM_TOKEN](../../kb-ultracs-datawarehouse/KWDW_ATM_TOKEN) | KBDOSOUTPUT2/DWBRCDET.TXT | Pipe-delimited (SEP is assigned '\|'; this written payload uses :SEP:) | WRITE; WRITESEQ |
| [KWDW_ATM_TOKEN](../../kb-ultracs-datawarehouse/KWDW_ATM_TOKEN) | KBDOSOUTPUT2/DWBRDEBC.TXT | Other / format not determined (no delimiter or fixed-width evidence tied to this output) | WRITE |
| [KWDW_ATM_TOKEN](../../kb-ultracs-datawarehouse/KWDW_ATM_TOKEN) | KBDOSOUTPUT2/DWCARDLK.TXT | Other / format not determined (no delimiter or fixed-width evidence tied to this output) | WRITE |
| [KWDW_ATM_TOKEN](../../kb-ultracs-datawarehouse/KWDW_ATM_TOKEN) | KBDOSOUTPUT2/DWCARDS.TXT | Pipe-delimited (SEP is assigned '\|'; this written payload uses :SEP:) | WRITE; WRITESEQ |
| [KWDW_AUDIT](../../kb-ultracs-datawarehouse/KWDW_AUDIT) | KBDOSOUTPUT/DWLOG.TXT | Other / format not determined (no delimiter or fixed-width evidence tied to this output) | WRITE |
| [KWDW_AUDIT](../../kb-ultracs-datawarehouse/KWDW_AUDIT) | KBDOSOUTPUT2/DWAUDIT.TXT | Pipe-delimited (SEP is assigned '\|'; this written payload uses :SEP:) | WRITE; WRITESEQ |
| [KWDW_AUDIT](../../kb-ultracs-datawarehouse/KWDW_AUDIT) | KBDOSOUTPUT2/DWCLACT.TXT | Pipe-delimited (SEP is assigned '\|'; this written payload uses :SEP:) | WRITE; WRITESEQ |
| [KWDW_AUTH1TO5](../../kb-ultracs-datawarehouse/KWDW_AUTH1TO5) | KBDOSOUTPUT/DWLOG.TXT | Other / format not determined (no delimiter or fixed-width evidence tied to this output) | WRITE |
| [KWDW_AUTH1TO5](../../kb-ultracs-datawarehouse/KWDW_AUTH1TO5) | KBDOSOUTPUT2/DWCDCAUTH1.TXT | Pipe-delimited (SEP is assigned '\|'; this written payload uses :SEP:) | WRITE; WRITESEQ |
| [KWDW_AUTH6TO10](../../kb-ultracs-datawarehouse/KWDW_AUTH6TO10) | KBDOSOUTPUT/DWLOG.TXT | Other / format not determined (no delimiter or fixed-width evidence tied to this output) | WRITE |
| [KWDW_AUTH6TO10](../../kb-ultracs-datawarehouse/KWDW_AUTH6TO10) | KBDOSOUTPUT2/DWCDCAUTH2.TXT | Pipe-delimited (SEP is assigned '\|'; this written payload uses :SEP:) | WRITE; WRITESEQ |
| [KWDW_BAL](../../kb-ultracs-datawarehouse/KWDW_BAL) | KBDOSOUTPUT/DWBAL.TXT | Pipe-delimited (SEP is assigned '\|'; this written payload uses :SEP:) | WRITE; WRITESEQ |
| [KWDW_BAL2](../../kb-ultracs-datawarehouse/KWDW_BAL2) | KBDOSOUTPUT/DWBAL.TXT | Pipe-delimited (SEP is assigned '\|'; this written payload uses :SEP:) | WRITE; WRITESEQ |
| [KWDW_BILLPAYPAYEE](../../kb-ultracs-datawarehouse/KWDW_BILLPAYPAYEE) | KBDOSOUTPUT/BILLPAYPAYEE.TXT | Pipe-delimited (SEP is assigned '\|'; this written payload uses :SEP:) | WRITE; WRITESEQ |
| [KWDW_BRS](../../kb-ultracs-datawarehouse/KWDW_BRS) | KBDOSOUTPUT/DWSAVBR.TXT | Pipe-delimited (SEP is assigned '\|'; this written payload uses :SEP:) | WRITE; WRITESEQ |
| [KWDW_CDCAUTH](../../kb-ultracs-datawarehouse/KWDW_CDCAUTH) | KBDOSOUTPUT2/DWCDCAUTH.TXT | Pipe-delimited (SEP is assigned '\|'; this written payload uses :SEP:) | WRITE; WRITESEQ |
| [KWDW_CHQS](../../kb-ultracs-datawarehouse/KWDW_CHQS) | KBDOSOUTPUT/DWLOG.TXT | Other / format not determined (no delimiter or fixed-width evidence tied to this output) | WRITE |
| [KWDW_CHQS](../../kb-ultracs-datawarehouse/KWDW_CHQS) | KBDOSOUTPUT2/DWCHQDEP.TXT | Other / format not determined (no delimiter or fixed-width evidence tied to this output) | WRITE; WRITESEQ |
| [KWDW_CHQS](../../kb-ultracs-datawarehouse/KWDW_CHQS) | KBDOSOUTPUT2/DWCHQIDX.TXT | Other / format not determined (no delimiter or fixed-width evidence tied to this output) | WRITE; WRITESEQ |
| [KWDW_CHQS](../../kb-ultracs-datawarehouse/KWDW_CHQS) | KBDOSOUTPUT2/DWCHQS.TXT | Pipe-delimited (SEP is assigned '\|'; this written payload uses :SEP:) | WRITE; WRITESEQ |
| [KWDW_CLACT](../../kb-ultracs-datawarehouse/KWDW_CLACT) | KBDOSOUTPUT/DWCLACT.TXT | Pipe-delimited (SEP is assigned '\|'; this written payload uses :SEP:) | WRITE; WRITESEQ |
| [KWDW_CLI](../../kb-ultracs-datawarehouse/KWDW_CLI) | KBDOSOUTPUT/DWLOG.TXT | Other / format not determined (no delimiter or fixed-width evidence tied to this output) | WRITE |
| [KWDW_CLI](../../kb-ultracs-datawarehouse/KWDW_CLI) | KBDOSOUTPUT2/CLIAPP.TXT | Other / format not determined (no delimiter or fixed-width evidence tied to this output) | WRITE |
| [KWDW_CLI](../../kb-ultracs-datawarehouse/KWDW_CLI) | KBDOSOUTPUT2/CLICONTRCT.TXT | Other / format not determined (no delimiter or fixed-width evidence tied to this output) | WRITE |
| [KWDW_CLI](../../kb-ultracs-datawarehouse/KWDW_CLI) | KBDOSOUTPUT2/CLIFXRATE.TXT | Other / format not determined (no delimiter or fixed-width evidence tied to this output) | WRITE |
| [KWDW_CLI](../../kb-ultracs-datawarehouse/KWDW_CLI) | KBDOSOUTPUT2/CLIFXRATEDET.TXT | Other / format not determined (no delimiter or fixed-width evidence tied to this output) | WRITE |
| [KWDW_CLI](../../kb-ultracs-datawarehouse/KWDW_CLI) | KBDOSOUTPUT2/CLIFXRATEH.TXT | Other / format not determined (no delimiter or fixed-width evidence tied to this output) | WRITE |
| [KWDW_CLI](../../kb-ultracs-datawarehouse/KWDW_CLI) | KBDOSOUTPUT2/CLIFXRATEHDET.TXT | Pipe-delimited (SEP is assigned '\|'; this written payload uses :SEP:) | WRITE; WRITESEQ |
| [KWDW_CLI](../../kb-ultracs-datawarehouse/KWDW_CLI) | KBDOSOUTPUT2/CLISECLK.TXT | Pipe-delimited (SEP is assigned '\|'; this written payload uses :SEP:) | WRITE; WRITESEQ |
| [KWDW_CLI](../../kb-ultracs-datawarehouse/KWDW_CLI) | KBDOSOUTPUT2/CLITYP.TXT | Other / format not determined (no delimiter or fixed-width evidence tied to this output) | WRITE |
| [KWDW_CLI](../../kb-ultracs-datawarehouse/KWDW_CLI) | KBDOSOUTPUT2/CLITYPH.TXT | Other / format not determined (no delimiter or fixed-width evidence tied to this output) | WRITE |
| [KWDW_CLI](../../kb-ultracs-datawarehouse/KWDW_CLI) | KBDOSOUTPUT2/DWTFREDIR.TXT | Pipe-delimited (SEP is assigned '\|'; this written payload uses :SEP:) | WRITE; WRITESEQ |
| [KWDW_CLID](../../kb-ultracs-datawarehouse/KWDW_CLID) | KBDOSOUTPUT/DWKBID.TXT | Pipe-delimited (SEP is assigned '\|'; this written payload uses :SEP:) | WRITE; WRITESEQ |
| [KWDW_CLID](../../kb-ultracs-datawarehouse/KWDW_CLID) | KBDOSOUTPUT/DWLOG.TXT | Other / format not determined (no delimiter or fixed-width evidence tied to this output) | WRITE |
| [KWDW_CLIENT](../../kb-ultracs-datawarehouse/KWDW_CLIENT) | KBDOSOUTPUT/DWBUSCL.TXT | Pipe-delimited (SEP is assigned '\|'; this written payload uses :SEP:) | WRITE; WRITESEQ |
| [KWDW_CLIENT](../../kb-ultracs-datawarehouse/KWDW_CLIENT) | KBDOSOUTPUT/DWBUSLINKS.TXT | Pipe-delimited (SEP is assigned '\|'; this written payload uses :SEP:) | WRITE; WRITESEQ |
| [KWDW_CLIENT](../../kb-ultracs-datawarehouse/KWDW_CLIENT) | KBDOSOUTPUT/DWBUSREL.TXT | Pipe-delimited (SEP is assigned '\|'; this written payload uses :SEP:) | WRITE; WRITESEQ |
| [KWDW_CLIENT](../../kb-ultracs-datawarehouse/KWDW_CLIENT) | KBDOSOUTPUT/DWCLUPD.TXT | Pipe-delimited (SEP is assigned '\|'; this written payload uses :SEP:) | WRITE; WRITESEQ |
| [KWDW_CLIENT](../../kb-ultracs-datawarehouse/KWDW_CLIENT) | KBDOSOUTPUT/DWLOG.TXT | Other / format not determined (no delimiter or fixed-width evidence tied to this output) | WRITE |
| [KWDW_CLIENT](../../kb-ultracs-datawarehouse/KWDW_CLIENT) | KBDOSOUTPUT2/DWALTCON.TXT | Pipe-delimited (SEP is assigned '\|'; this written payload uses :SEP:) | WRITE; WRITESEQ |
| [KWDW_CLIENTCLASS](../../kb-ultracs-datawarehouse/KWDW_CLIENTCLASS) | KBDOSOUTPUT/CLIENTCLASS.TXT | Pipe-delimited (SEP is assigned '\|'; this written payload uses :SEP:) | WRITE; WRITESEQ |
| [KWDW_CLIENTX](../../kb-ultracs-datawarehouse/KWDW_CLIENTX) | KBDOSOUTPUT/DWCLUPD.TXT | Pipe-delimited (SEP is assigned '\|'; this written payload uses :SEP:) | WRITE; WRITESEQ |
| [KWDW_CLIENTX](../../kb-ultracs-datawarehouse/KWDW_CLIENTX) | KBDOSOUTPUT/DWIVRLOG.TXT | Pipe-delimited (SEP is assigned '\|'; this written payload uses :SEP:) | WRITE; WRITESEQ |
| [KWDW_CLIENTX](../../kb-ultracs-datawarehouse/KWDW_CLIENTX) | KBDOSOUTPUT/DWLOG.TXT | Other / format not determined (no delimiter or fixed-width evidence tied to this output) | WRITE |
| [KWDW_CLIENTX](../../kb-ultracs-datawarehouse/KWDW_CLIENTX) | KBDOSOUTPUT/DWRBILOG.TXT | Pipe-delimited (SEP is assigned '\|'; this written payload uses :SEP:) | WRITE; WRITESEQ |
| [KWDW_CLRUN](../../kb-ultracs-datawarehouse/KWDW_CLRUN) | KBDOSOUTPUT/CONTROL_CL.TXT | Other / format not determined (no delimiter or fixed-width evidence tied to this output) | WRITE |
| [KWDW_CLRUN](../../kb-ultracs-datawarehouse/KWDW_CLRUN) | KBDOSOUTPUT/CONTROL_CL2.TXT | Other / format not determined (no delimiter or fixed-width evidence tied to this output) | WRITE |
| [KWDW_CLRUN](../../kb-ultracs-datawarehouse/KWDW_CLRUN) | KBDOSOUTPUT/DWCLOG.TXT | Pipe-delimited (SEP is assigned '\|'; this written payload uses :SEP:) | WRITE |
| [KWDW_CLRUN_AUTO](../../kb-ultracs-datawarehouse/KWDW_CLRUN_AUTO) | KBDOSOUTPUT/CLIENTEXTRACTGOODTOGO.TXT | Other / format not determined (no delimiter or fixed-width evidence tied to this output) | WRITE |
| [KWDW_CLRUN_AUTO](../../kb-ultracs-datawarehouse/KWDW_CLRUN_AUTO) | KBDOSOUTPUT/CONTROL_CL.TXT | Other / format not determined (no delimiter or fixed-width evidence tied to this output) | WRITE |
| [KWDW_CLRUN_AUTO](../../kb-ultracs-datawarehouse/KWDW_CLRUN_AUTO) | KBDOSOUTPUT/CONTROL_CL2.TXT | Other / format not determined (no delimiter or fixed-width evidence tied to this output) | WRITE |
| [KWDW_CLRUN_AUTO](../../kb-ultracs-datawarehouse/KWDW_CLRUN_AUTO) | KBDOSOUTPUT/DWCLOG.TXT | Pipe-delimited (SEP is assigned '\|'; this written payload uses :SEP:) | WRITE |
| [KWDW_DDAUTH](../../kb-ultracs-datawarehouse/KWDW_DDAUTH) | KBDOSOUTPUT/DWLOG.TXT | Other / format not determined (no delimiter or fixed-width evidence tied to this output) | WRITE |
| [KWDW_DDAUTH](../../kb-ultracs-datawarehouse/KWDW_DDAUTH) | KBDOSOUTPUT2/DWDDAUTH2.TXT | Pipe-delimited (SEP is assigned '\|'; this written payload uses :SEP:) | WRITE; WRITESEQ |
| [KWDW_DEBIT](../../kb-ultracs-datawarehouse/KWDW_DEBIT) | KBDOSOUTPUT/DWLOG.TXT | Other / format not determined (no delimiter or fixed-width evidence tied to this output) | WRITE |
| [KWDW_DEBIT](../../kb-ultracs-datawarehouse/KWDW_DEBIT) | KBDOSOUTPUT2/DWCDC.TXT | Pipe-delimited (SEP is assigned '\|'; this written payload uses :SEP:) | WRITE; WRITESEQ |
| [KWDW_DEBIT](../../kb-ultracs-datawarehouse/KWDW_DEBIT) | KBDOSOUTPUT2/DWCDCACC.TXT | Pipe-delimited (SEP is assigned '\|'; this written payload uses :SEP:) | WRITE; WRITESEQ |
| [KWDW_DEBIT](../../kb-ultracs-datawarehouse/KWDW_DEBIT) | KBDOSOUTPUT2/DWCDCLK.TXT | Pipe-delimited (SEP is assigned '\|'; this written payload uses :SEP:) | WRITE; WRITESEQ |
| [KWDW_DEBIT](../../kb-ultracs-datawarehouse/KWDW_DEBIT) | KBDOSOUTPUT2/DWCDCREQ.TXT | Pipe-delimited (SEP is assigned '\|'; this written payload uses :SEP:) | WRITE; WRITESEQ |
| [KWDW_DEBIT_TOKEN](../../kb-ultracs-datawarehouse/KWDW_DEBIT_TOKEN) | KBDOSOUTPUT2/DWCDC.TXT | Pipe-delimited (SEP is assigned '\|'; this written payload uses :SEP:) | WRITE; WRITESEQ |
| [KWDW_DEBIT_TOKEN](../../kb-ultracs-datawarehouse/KWDW_DEBIT_TOKEN) | KBDOSOUTPUT2/DWCDCACC.TXT | Pipe-delimited (SEP is assigned '\|'; this written payload uses :SEP:) | WRITE; WRITESEQ |
| [KWDW_DEBIT_TOKEN](../../kb-ultracs-datawarehouse/KWDW_DEBIT_TOKEN) | KBDOSOUTPUT2/DWCDCLK.TXT | Pipe-delimited (SEP is assigned '\|'; this written payload uses :SEP:) | WRITE; WRITESEQ |
| [KWDW_DEBIT_TOKEN](../../kb-ultracs-datawarehouse/KWDW_DEBIT_TOKEN) | KBDOSOUTPUT2/DWCDCREQ.TXT | Pipe-delimited (SEP is assigned '\|'; this written payload uses :SEP:) | WRITE; WRITESEQ |
| [KWDW_DESDDA](../../kb-ultracs-datawarehouse/KWDW_DESDDA) | KBDOSOUTPUT/DWKWDDA.TXT | Pipe-delimited (SEP is assigned '\|'; this written payload uses :SEP:) | WRITE; WRITESEQ |
| [KWDW_DESDDA](../../kb-ultracs-datawarehouse/KWDW_DESDDA) | KBDOSOUTPUT/DWLOG.TXT | Other / format not determined (no delimiter or fixed-width evidence tied to this output) | WRITE |
| [KWDW_DESOUT](../../kb-ultracs-datawarehouse/KWDW_DESOUT) | KBDOSOUTPUT/DESCNTL.TXT | Other / format not determined (no delimiter or fixed-width evidence tied to this output) | WRITEV |
| [KWDW_DESOUT](../../kb-ultracs-datawarehouse/KWDW_DESOUT) | KBDOSOUTPUT/DWDESOUT.TXT | Pipe-delimited (SEP is assigned '\|'; this written payload uses :SEP:) | WRITE; WRITESEQ |
| [KWDW_DESPAYEE](../../kb-ultracs-datawarehouse/KWDW_DESPAYEE) | KBDOSOUTPUT/DESPAYEE.TXT | Pipe-delimited (SEP is assigned '\|'; this written payload uses :SEP:) | WRITE; WRITESEQ |
| [KWDW_EASYCODES](../../kb-ultracs-datawarehouse/KWDW_EASYCODES) | KBDOSOUTPUT/DWAMPGRP.TXT | Other / format not determined (no delimiter or fixed-width evidence tied to this output) | WRITE |
| [KWDW_EASYCODES](../../kb-ultracs-datawarehouse/KWDW_EASYCODES) | KBDOSOUTPUT/DWBRLCD.TXT | Other / format not determined (no delimiter or fixed-width evidence tied to this output) | WRITE |
| [KWDW_EASYCODES](../../kb-ultracs-datawarehouse/KWDW_EASYCODES) | KBDOSOUTPUT/DWBRLCOM.TXT | Other / format not determined (no delimiter or fixed-width evidence tied to this output) | WRITE |
| [KWDW_EASYCODES](../../kb-ultracs-datawarehouse/KWDW_EASYCODES) | KBDOSOUTPUT/DWBRLRT.TXT | Other / format not determined (no delimiter or fixed-width evidence tied to this output) | WRITE |
| [KWDW_EASYCODES](../../kb-ultracs-datawarehouse/KWDW_EASYCODES) | KBDOSOUTPUT/DWEASYCD.TXT | Other / format not determined (no delimiter or fixed-width evidence tied to this output) | WRITE |
| [KWDW_EASYCODES](../../kb-ultracs-datawarehouse/KWDW_EASYCODES) | KBDOSOUTPUT/DWLOG.TXT | Other / format not determined (no delimiter or fixed-width evidence tied to this output) | WRITE |
| [KWDW_FEE](../../kb-ultracs-datawarehouse/KWDW_FEE) | KBDOSOUTPUT/DWFEE605.TXT | Pipe-delimited (SEP is assigned '\|'; this written payload uses :SEP:) | WRITE; WRITESEQ |
| [KWDW_FEE](../../kb-ultracs-datawarehouse/KWDW_FEE) | KBDOSOUTPUT/DWLOG.TXT | Other / format not determined (no delimiter or fixed-width evidence tied to this output) | WRITE |
| [KWDW_GCSLOG](../../kb-ultracs-datawarehouse/KWDW_GCSLOG) | KBDOSOUTPUT | Pipe-delimited (SEP is assigned '\|'; this written payload uses :SEP:) | WRITESEQ |
| [KWDW_GCSLOG](../../kb-ultracs-datawarehouse/KWDW_GCSLOG) | KBDOSOUTPUT/DWLOG.TXT | Other / format not determined (no delimiter or fixed-width evidence tied to this output) | WRITE |
| [KWDW_GCSLOG](../../kb-ultracs-datawarehouse/KWDW_GCSLOG) | KBDOSOUTPUT/DYNAMIC(FID) | Other / format not determined (no delimiter or fixed-width evidence tied to this output) | WRITE |
| [KWDW_GLTRAN](../../kb-ultracs-datawarehouse/KWDW_GLTRAN) | KBDOSOUTPUT/DWGLDUMP.TXT | Pipe-delimited (SEP is assigned '\|'; this written payload uses :SEP:) | WRITE; WRITESEQ |
| [KWDW_GLTRAN](../../kb-ultracs-datawarehouse/KWDW_GLTRAN) | KBDOSOUTPUT/DWLOG.TXT | Other / format not determined (no delimiter or fixed-width evidence tied to this output) | WRITE |
| [KWDW_GLTRAN](../../kb-ultracs-datawarehouse/KWDW_GLTRAN) | KBDOSOUTPUT2/DWGLACC.TXT | Other / format not determined (no delimiter or fixed-width evidence tied to this output) | WRITE |
| [KWDW_INS](../../kb-ultracs-datawarehouse/KWDW_INS) | KBDOSOUTPUT/DWARINS.TXT | Other / format not determined (no delimiter or fixed-width evidence tied to this output) | WRITE |
| [KWDW_INS](../../kb-ultracs-datawarehouse/KWDW_INS) | KBDOSOUTPUT/DWBNINS.TXT | Pipe-delimited (SEP is assigned '\|'; this written payload uses :SEP:) | WRITE; WRITESEQ |
| [KWDW_INS](../../kb-ultracs-datawarehouse/KWDW_INS) | KBDOSOUTPUT/DWKWINS.TXT | Pipe-delimited (SEP is assigned '\|'; this written payload uses :SEP:) | WRITE; WRITESEQ |
| [KWDW_INS](../../kb-ultracs-datawarehouse/KWDW_INS) | KBDOSOUTPUT/DWLNINS.TXT | Pipe-delimited (SEP is assigned '\|'; this written payload uses :SEP:) | WRITE; WRITESEQ |
| [KWDW_INS](../../kb-ultracs-datawarehouse/KWDW_INS) | KBDOSOUTPUT/DWLOG.TXT | Other / format not determined (no delimiter or fixed-width evidence tied to this output) | WRITE |
| [KWDW_INS](../../kb-ultracs-datawarehouse/KWDW_INS) | KBDOSOUTPUT/DWPREM.TXT | Pipe-delimited (SEP is assigned '\|'; this written payload uses :SEP:) | WRITE; WRITESEQ |
| [KWDW_INTERNALTRANSFER](../../kb-ultracs-datawarehouse/KWDW_INTERNALTRANSFER) | KBDOSOUTPUT/INTERNALTRANSFER.TXT | Pipe-delimited (SEP is assigned '\|'; this written payload uses :SEP:) | WRITE; WRITESEQ |
| [KWDW_IVRCLIENTPAYEE](../../kb-ultracs-datawarehouse/KWDW_IVRCLIENTPAYEE) | KBDOSOUTPUT/IVRCLIENTPAYEE.TXT | Pipe-delimited (SEP is assigned '\|'; this written payload uses :SEP:) | WRITE; WRITESEQ |
| [KWDW_IVRFULL](../../kb-ultracs-datawarehouse/KWDW_IVRFULL) | KBDOSOUTPUT/IVRCLIENT.TXT | Pipe-delimited (SEP is assigned '\|'; this written payload uses :SEP:) | WRITE; WRITESEQ |
| [KWDW_IVRLOGNEW](../../kb-ultracs-datawarehouse/KWDW_IVRLOGNEW) | KBDOSOUTPUT/IVRCALLLOG.TXT | Pipe-delimited (SEP is assigned '\|'; this written payload uses :SEP:) | WRITE; WRITESEQ |
| [KWDW_LETTERS](../../kb-ultracs-datawarehouse/KWDW_LETTERS) | KBDOSOUTPUT/DWLETTER.TXT | Pipe-delimited (SEP is assigned '\|'; this written payload uses :SEP:) | WRITE; WRITESEQ |
| [KWDW_LETTERS](../../kb-ultracs-datawarehouse/KWDW_LETTERS) | KBDOSOUTPUT/DWLOG.TXT | Other / format not determined (no delimiter or fixed-width evidence tied to this output) | WRITE |
| [KWDW_LN](../../kb-ultracs-datawarehouse/KWDW_LN) | KBDOSOUTPUT/DWLOG.TXT | Other / format not determined (no delimiter or fixed-width evidence tied to this output) | WRITE |
| [KWDW_LN](../../kb-ultracs-datawarehouse/KWDW_LN) | KBDOSOUTPUT/DWSTMTLOANS.CTL | Other / format not determined (no delimiter or fixed-width evidence tied to this output) | WRITE |
| [KWDW_LN](../../kb-ultracs-datawarehouse/KWDW_LN) | KBDOSOUTPUT/DWSTMTLOANS.TXT | Pipe-delimited (SEP is assigned '\|'; this written payload uses :SEP:) | WRITE; WRITESEQ |
| [KWDW_LOANS](../../kb-ultracs-datawarehouse/KWDW_LOANS) | KBDOSOUTPUT/DWFREP.TXT | Pipe-delimited (SEP is assigned '\|'; this written payload uses :SEP:) | WRITE; WRITESEQ |
| [KWDW_LOANS](../../kb-ultracs-datawarehouse/KWDW_LOANS) | KBDOSOUTPUT/DWKWLOAN.TXT | Pipe-delimited (SEP is assigned '\|'; this written payload uses :SEP:) | WRITE; WRITESEQ |
| [KWDW_LOANS](../../kb-ultracs-datawarehouse/KWDW_LOANS) | KBDOSOUTPUT/DWLNBRL.TXT | Pipe-delimited (SEP is assigned '\|'; this written payload uses :SEP:) | WRITE; WRITESEQ |
| [KWDW_LOANS](../../kb-ultracs-datawarehouse/KWDW_LOANS) | KBDOSOUTPUT/DWLNPMTS.TXT | Pipe-delimited (SEP is assigned '\|'; this written payload uses :SEP:) | WRITE; WRITESEQ |
| [KWDW_LOANS](../../kb-ultracs-datawarehouse/KWDW_LOANS) | KBDOSOUTPUT/DWLNRVL.TXT | Pipe-delimited (SEP is assigned '\|'; this written payload uses :SEP:) | WRITE; WRITESEQ |
| [KWDW_LOANS](../../kb-ultracs-datawarehouse/KWDW_LOANS) | KBDOSOUTPUT/DWLOG.TXT | Other / format not determined (no delimiter or fixed-width evidence tied to this output) | WRITE |
| [KWDW_LRATES](../../kb-ultracs-datawarehouse/KWDW_LRATES) | KBDOSOUTPUT/DWLOG.TXT | Other / format not determined (no delimiter or fixed-width evidence tied to this output) | WRITE |
| [KWDW_LRATES](../../kb-ultracs-datawarehouse/KWDW_LRATES) | KBDOSOUTPUT/DWLRATE.TXT | Pipe-delimited (SEP is assigned '\|'; this written payload uses :SEP:) | WRITE; WRITESEQ |
| [KWDW_LRATES](../../kb-ultracs-datawarehouse/KWDW_LRATES) | KBDOSOUTPUT/DWLRATE2.TXT | Pipe-delimited (SEP is assigned '\|'; this written payload uses :SEP:) | WRITE; WRITESEQ |
| [KWDW_MOBTXT](../../kb-ultracs-datawarehouse/KWDW_MOBTXT) | KBDOSOUTPUT/DWLOG.TXT | Other / format not determined (no delimiter or fixed-width evidence tied to this output) | WRITE |
| [KWDW_MOBTXT](../../kb-ultracs-datawarehouse/KWDW_MOBTXT) | KBDOSOUTPUT/DWMOBTXT.TXT | Pipe-delimited (SEP is assigned '\|'; this written payload uses :SEP:) | WRITE; WRITESEQ |
| [KWDW_NAUDIT](../../kb-ultracs-datawarehouse/KWDW_NAUDIT) | KBDOSOUTPUT/DWLOG.TXT | Other / format not determined (no delimiter or fixed-width evidence tied to this output) | WRITE |
| [KWDW_NAUDIT](../../kb-ultracs-datawarehouse/KWDW_NAUDIT) | KBDOSOUTPUT2/DWAUDIT_ | Pipe-delimited (SEP is assigned '\|'; this written payload uses :SEP:) | WRITESEQ |
| [KWDW_NAUDIT](../../kb-ultracs-datawarehouse/KWDW_NAUDIT) | KBDOSOUTPUT2/DWAUDIT_/.TXT | Other / format not determined (no delimiter or fixed-width evidence tied to this output) | WRITE |
| [KWDW_NOMACC](../../kb-ultracs-datawarehouse/KWDW_NOMACC) | KBDOSOUTPUT/DWLOG.TXT | Other / format not determined (no delimiter or fixed-width evidence tied to this output) | WRITE |
| [KWDW_NOMACC](../../kb-ultracs-datawarehouse/KWDW_NOMACC) | KBDOSOUTPUT/DWNOMACC.TXT | Pipe-delimited (SEP is assigned '\|'; this written payload uses :SEP:) | WRITE; WRITESEQ |
| [KWDW_NZHL](../../kb-ultracs-datawarehouse/KWDW_NZHL) | KBDOSOUTPUT/DWAMP.TXT | Pipe-delimited (SEP is assigned '\|'; this written payload uses :SEP:) | WRITE; WRITESEQ |
| [KWDW_NZHL](../../kb-ultracs-datawarehouse/KWDW_NZHL) | KBDOSOUTPUT/DWLOG.TXT | Other / format not determined (no delimiter or fixed-width evidence tied to this output) | WRITE |
| [KWDW_NZHL](../../kb-ultracs-datawarehouse/KWDW_NZHL) | KBDOSOUTPUT/DWNZHL.TXT | Pipe-delimited (SEP is assigned '\|'; this written payload uses :SEP:) | WRITE; WRITESEQ |
| [KWDW_P98TC](../../kb-ultracs-datawarehouse/KWDW_P98TC) | KBDOSOUTPUT/DWLOG.TXT | Other / format not determined (no delimiter or fixed-width evidence tied to this output) | WRITE |
| [KWDW_P98TC](../../kb-ultracs-datawarehouse/KWDW_P98TC) | KBDOSOUTPUT2/DWP98TC.TXT | Other / format not determined (no delimiter or fixed-width evidence tied to this output) | WRITE |
| [KWDW_P98TC](../../kb-ultracs-datawarehouse/KWDW_P98TC) | KBDOSOUTPUT2/DWTF503.TXT | Other / format not determined (no delimiter or fixed-width evidence tied to this output) | WRITE |
| [KWDW_PART3](../../kb-ultracs-datawarehouse/KWDW_PART3) | KBDOSOUTPUT/AMORTCONTROL.TXT | Other / format not determined (no delimiter or fixed-width evidence tied to this output) | WRITE |
| [KWDW_PART3](../../kb-ultracs-datawarehouse/KWDW_PART3) | KBDOSOUTPUT/CONTROL_CL2.TXT | Other / format not determined (no delimiter or fixed-width evidence tied to this output) | WRITE |
| [KWDW_PART3](../../kb-ultracs-datawarehouse/KWDW_PART3) | KBDOSOUTPUT/DWACC{HEAD} | Other / format not determined (no delimiter or fixed-width evidence tied to this output) | WRITE |
| [KWDW_PART3](../../kb-ultracs-datawarehouse/KWDW_PART3) | KBDOSOUTPUT/DWISUMM.TXT | Other / format not determined (no delimiter or fixed-width evidence tied to this output) | WRITE |
| [KWDW_PART3](../../kb-ultracs-datawarehouse/KWDW_PART3) | KBDOSOUTPUT/DWLOG.TXT | Other / format not determined (no delimiter or fixed-width evidence tied to this output) | WRITE |
| [KWDW_PART3](../../kb-ultracs-datawarehouse/KWDW_PART3) | KBDOSOUTPUT/DWREL{HEAD} | Other / format not determined (no delimiter or fixed-width evidence tied to this output) | WRITE |
| [KWDW_PART3](../../kb-ultracs-datawarehouse/KWDW_PART3) | KBDOSOUTPUT/DWREP.TXT | Other / format not determined (no delimiter or fixed-width evidence tied to this output) | WRITE |
| [KWDW_PART3](../../kb-ultracs-datawarehouse/KWDW_PART3) | KBDOSOUTPUT/DWSAVBR.TXT | Other / format not determined (no delimiter or fixed-width evidence tied to this output) | WRITE |
| [KWDW_PART3](../../kb-ultracs-datawarehouse/KWDW_PART3) | KBDOSOUTPUT/DWTDS.TXT | Other / format not determined (no delimiter or fixed-width evidence tied to this output) | WRITE |
| [KWDW_PART3](../../kb-ultracs-datawarehouse/KWDW_PART3) | KBDOSOUTPUT/DWUNCLD.TXT | Other / format not determined (no delimiter or fixed-width evidence tied to this output) | WRITE |
| [KWDW_PART3](../../kb-ultracs-datawarehouse/KWDW_PART3) | KBDOSOUTPUT/ZCONTROL1.TXT | Other / format not determined (no delimiter or fixed-width evidence tied to this output) | WRITE |
| [KWDW_PART3_AUTO](../../kb-ultracs-datawarehouse/KWDW_PART3_AUTO) | KBDOSOUTPUT/CONTROL_CL2.TXT | Other / format not determined (no delimiter or fixed-width evidence tied to this output) | WRITE |
| [KWDW_PART3_AUTO](../../kb-ultracs-datawarehouse/KWDW_PART3_AUTO) | KBDOSOUTPUT/DWACC{HEAD} | Other / format not determined (no delimiter or fixed-width evidence tied to this output) | WRITE |
| [KWDW_PART3_AUTO](../../kb-ultracs-datawarehouse/KWDW_PART3_AUTO) | KBDOSOUTPUT/DWISUMM.TXT | Other / format not determined (no delimiter or fixed-width evidence tied to this output) | WRITE |
| [KWDW_PART3_AUTO](../../kb-ultracs-datawarehouse/KWDW_PART3_AUTO) | KBDOSOUTPUT/DWLOG.TXT | Other / format not determined (no delimiter or fixed-width evidence tied to this output) | WRITE |
| [KWDW_PART3_AUTO](../../kb-ultracs-datawarehouse/KWDW_PART3_AUTO) | KBDOSOUTPUT/DWREL{HEAD} | Other / format not determined (no delimiter or fixed-width evidence tied to this output) | WRITE |
| [KWDW_PART3_AUTO](../../kb-ultracs-datawarehouse/KWDW_PART3_AUTO) | KBDOSOUTPUT/DWREP.TXT | Other / format not determined (no delimiter or fixed-width evidence tied to this output) | WRITE |
| [KWDW_PART3_AUTO](../../kb-ultracs-datawarehouse/KWDW_PART3_AUTO) | KBDOSOUTPUT/DWSAVBR.TXT | Other / format not determined (no delimiter or fixed-width evidence tied to this output) | WRITE |
| [KWDW_PART3_AUTO](../../kb-ultracs-datawarehouse/KWDW_PART3_AUTO) | KBDOSOUTPUT/DWTDS.TXT | Other / format not determined (no delimiter or fixed-width evidence tied to this output) | WRITE |
| [KWDW_PART3_AUTO](../../kb-ultracs-datawarehouse/KWDW_PART3_AUTO) | KBDOSOUTPUT/DWUNCLD.TXT | Other / format not determined (no delimiter or fixed-width evidence tied to this output) | WRITE |
| [KWDW_PART3_AUTO](../../kb-ultracs-datawarehouse/KWDW_PART3_AUTO) | KBDOSOUTPUT/ZCONTROL1.TXT | Other / format not determined (no delimiter or fixed-width evidence tied to this output) | WRITE |
| [KWDW_PIE](../../kb-ultracs-datawarehouse/KWDW_PIE) | KBDOSOUTPUT/DWLOG.TXT | Other / format not determined (no delimiter or fixed-width evidence tied to this output) | WRITE |
| [KWDW_PIE](../../kb-ultracs-datawarehouse/KWDW_PIE) | KBDOSOUTPUT2/DWPIE.TXT | Pipe-delimited (SEP is assigned '\|'; this written payload uses :SEP:) | WRITE; WRITESEQ |
| [KWDW_PP](../../kb-ultracs-datawarehouse/KWDW_PP) | KBDOSOUTPUT/DWLOG.TXT | Other / format not determined (no delimiter or fixed-width evidence tied to this output) | WRITE |
| [KWDW_PP](../../kb-ultracs-datawarehouse/KWDW_PP) | KBDOSOUTPUT/DWPP.TXT | Pipe-delimited (SEP is assigned '\|'; this written payload uses :SEP:) | WRITE; WRITESEQ |
| [KWDW_PP.old](../../kb-ultracs-datawarehouse/KWDW_PP.old) | KBDOSOUTPUT/DWLOG.TXT | Other / format not determined (no delimiter or fixed-width evidence tied to this output) | WRITE |
| [KWDW_PP.old](../../kb-ultracs-datawarehouse/KWDW_PP.old) | KBDOSOUTPUT/DWPP.TXT | Pipe-delimited (SEP is assigned '\|'; this written payload uses :SEP:) | WRITE; WRITESEQ |
| [KWDW_PRIVATEPAYEE](../../kb-ultracs-datawarehouse/KWDW_PRIVATEPAYEE) | KBDOSOUTPUT/PRIVATEPAYEE.TXT | Pipe-delimited (SEP is assigned '\|'; this written payload uses :SEP:) | WRITE; WRITESEQ |
| [KWDW_PSTREAM](../../kb-ultracs-datawarehouse/KWDW_PSTREAM) | KBDOSOUTPUT2/DWPSTRM1.TXT | Pipe-delimited (SEP is assigned '\|'; this written payload uses :SEP:) | WRITE; WRITESEQ |
| [KWDW_PSTREAM](../../kb-ultracs-datawarehouse/KWDW_PSTREAM) | KBDOSOUTPUT2/DWPSTRM2.TXT | Pipe-delimited (SEP is assigned '\|'; this written payload uses :SEP:) | WRITE; WRITESEQ |
| [KWDW_PUBLICPAYEE](../../kb-ultracs-datawarehouse/KWDW_PUBLICPAYEE) | KBDOSOUTPUT/PUBLICPAYEE.TXT | Pipe-delimited (SEP is assigned '\|'; this written payload uses :SEP:) | WRITE; WRITESEQ |
| [KWDW_RATES](../../kb-ultracs-datawarehouse/KWDW_RATES) | KBDOSOUTPUT/DWHOLS.TXT | Other / format not determined (no delimiter or fixed-width evidence tied to this output) | WRITE; WRITESEQ |
| [KWDW_RATES](../../kb-ultracs-datawarehouse/KWDW_RATES) | KBDOSOUTPUT/DWIRATES.TXT | Pipe-delimited (SEP is assigned '\|'; this written payload uses :SEP:) | WRITE; WRITESEQ |
| [KWDW_RATES](../../kb-ultracs-datawarehouse/KWDW_RATES) | KBDOSOUTPUT/DWLOG.TXT | Other / format not determined (no delimiter or fixed-width evidence tied to this output) | WRITE |
| [KWDW_RATES](../../kb-ultracs-datawarehouse/KWDW_RATES) | KBDOSOUTPUT/DWLRATES.TXT | Pipe-delimited (SEP is assigned '\|'; this written payload uses :SEP:) | WRITE; WRITESEQ |
| [KWDW_RATES](../../kb-ultracs-datawarehouse/KWDW_RATES) | KBDOSOUTPUT/DWSNPA.TXT | Other / format not determined (no delimiter or fixed-width evidence tied to this output) | WRITE |
| [KWDW_RATES](../../kb-ultracs-datawarehouse/KWDW_RATES) | KBDOSOUTPUT/DWSRATES.TXT | Pipe-delimited (SEP is assigned '\|'; this written payload uses :SEP:) | WRITE; WRITESEQ |
| [KWDW_RATES](../../kb-ultracs-datawarehouse/KWDW_RATES) | KBDOSOUTPUT/DWTDTIER.TXT | Pipe-delimited (SEP is assigned '\|'; this written payload uses :SEP:) | WRITE; WRITESEQ |
| [KWDW_RATES](../../kb-ultracs-datawarehouse/KWDW_RATES) | KBDOSOUTPUT/DWTIERS.TXT | Pipe-delimited (SEP is assigned '\|'; this written payload uses :SEP:) | WRITE; WRITESEQ |
| [KWDW_RATESC](../../kb-ultracs-datawarehouse/KWDW_RATESC) | KBDOSOUTPUT/DWCIRATES.TXT | Pipe-delimited (SEP is assigned '\|'; this written payload uses :SEP:) | WRITE; WRITESEQ |
| [KWDW_RATESC](../../kb-ultracs-datawarehouse/KWDW_RATESC) | KBDOSOUTPUT/DWCLRATES.TXT | Pipe-delimited (SEP is assigned '\|'; this written payload uses :SEP:) | WRITE; WRITESEQ |
| [KWDW_RATESC](../../kb-ultracs-datawarehouse/KWDW_RATESC) | KBDOSOUTPUT/DWCSNPA.TXT | Other / format not determined (no delimiter or fixed-width evidence tied to this output) | WRITE |
| [KWDW_RATESC](../../kb-ultracs-datawarehouse/KWDW_RATESC) | KBDOSOUTPUT/DWCSRATES.TXT | Pipe-delimited (SEP is assigned '\|'; this written payload uses :SEP:) | WRITE; WRITESEQ |
| [KWDW_RATESC](../../kb-ultracs-datawarehouse/KWDW_RATESC) | KBDOSOUTPUT/DWCTDTIER.TXT | Pipe-delimited (SEP is assigned '\|'; this written payload uses :SEP:) | WRITE; WRITESEQ |
| [KWDW_RATESC](../../kb-ultracs-datawarehouse/KWDW_RATESC) | KBDOSOUTPUT/DWCTIERS.TXT | Pipe-delimited (SEP is assigned '\|'; this written payload uses :SEP:) | WRITE; WRITESEQ |
| [KWDW_RATESC](../../kb-ultracs-datawarehouse/KWDW_RATESC) | KBDOSOUTPUT/DWLOG.TXT | Other / format not determined (no delimiter or fixed-width evidence tied to this output) | WRITE |
| [KWDW_RBI](../../kb-ultracs-datawarehouse/KWDW_RBI) | KBDOSOUTPUT/DWLOG.TXT | Other / format not determined (no delimiter or fixed-width evidence tied to this output) | WRITE |
| [KWDW_RBI](../../kb-ultracs-datawarehouse/KWDW_RBI) | KBDOSOUTPUT/DWRBIDET.TXT | Other / format not determined (no delimiter or fixed-width evidence tied to this output) | WRITE; WRITESEQ |
| [KWDW_RBI](../../kb-ultracs-datawarehouse/KWDW_RBI) | KBDOSOUTPUT/DWRBIIDX.TXT | Pipe-delimited (SEP is assigned '\|'; this written payload uses :SEP:) | WRITE; WRITESEQ |
| [KWDW_RBI2](../../kb-ultracs-datawarehouse/KWDW_RBI2) | KBDOSOUTPUT/KBRBI2.TXT | Pipe-delimited (SEP is assigned '\|'; this written payload uses :SEP:) | WRITE; WRITESEQ |
| [KWDW_RBIFULL](../../kb-ultracs-datawarehouse/KWDW_RBIFULL) | KBDOSOUTPUT/RBIUSER.TXT | Pipe-delimited (SEP is assigned '\|'; this written payload uses :SEP:) | WRITE; WRITESEQ |
| [KWDW_REP](../../kb-ultracs-datawarehouse/KWDW_REP) | KBDOSOUTPUT/DWLNPMTSB.TXT | Pipe-delimited (SEP is assigned '\|'; this written payload uses :SEP:) | WRITE; WRITESEQ |
| [KWDW_REP](../../kb-ultracs-datawarehouse/KWDW_REP) | KBDOSOUTPUT/DWLNPMTSF.TXT | Pipe-delimited (SEP is assigned '\|'; this written payload uses :SEP:) | WRITE; WRITESEQ |
| [KWDW_REP](../../kb-ultracs-datawarehouse/KWDW_REP) | KBDOSOUTPUT/DWLOG.TXT | Other / format not determined (no delimiter or fixed-width evidence tied to this output) | WRITE |
| [KWDW_RHIST](../../kb-ultracs-datawarehouse/KWDW_RHIST) | KBDOSOUTPUT/DWIHIST.TXT | Pipe-delimited (SEP is assigned '\|'; this written payload uses :SEP:) | WRITE; WRITESEQ |
| [KWDW_RHIST](../../kb-ultracs-datawarehouse/KWDW_RHIST) | KBDOSOUTPUT/DWIHISTT.TXT | Pipe-delimited (SEP is assigned '\|'; this written payload uses :SEP:) | WRITE; WRITESEQ |
| [KWDW_RHIST](../../kb-ultracs-datawarehouse/KWDW_RHIST) | KBDOSOUTPUT/DWLHIST.TXT | Pipe-delimited (SEP is assigned '\|'; this written payload uses :SEP:) | WRITE; WRITESEQ |
| [KWDW_RHIST](../../kb-ultracs-datawarehouse/KWDW_RHIST) | KBDOSOUTPUT/DWLOG.TXT | Other / format not determined (no delimiter or fixed-width evidence tied to this output) | WRITE |
| [KWDW_RHIST](../../kb-ultracs-datawarehouse/KWDW_RHIST) | KBDOSOUTPUT/DWSHIST.TXT | Pipe-delimited (SEP is assigned '\|'; this written payload uses :SEP:) | WRITE; WRITESEQ |
| [KWDW_RHIST](../../kb-ultracs-datawarehouse/KWDW_RHIST) | KBDOSOUTPUT/DWSTIER.TXT | Pipe-delimited (SEP is assigned '\|'; this written payload uses :SEP:) | WRITE; WRITESEQ |
| [KWDW_SAVEJ](../../kb-ultracs-datawarehouse/KWDW_SAVEJ) | KBDOSOUTPUT/DWLOG.TXT | Other / format not determined (no delimiter or fixed-width evidence tied to this output) | WRITE |
| [KWDW_SAVEJ](../../kb-ultracs-datawarehouse/KWDW_SAVEJ) | KBDOSOUTPUT2/DWSAVEJ.TXT | Pipe-delimited (SEP is assigned '\|'; this written payload uses :SEP:) | WRITE; WRITESEQ |
| [KWDW_SCHEDOD](../../kb-ultracs-datawarehouse/KWDW_SCHEDOD) | KBDOSOUTPUT/DWLOG.TXT | Other / format not determined (no delimiter or fixed-width evidence tied to this output) | WRITE |
| [KWDW_SCHEDOD](../../kb-ultracs-datawarehouse/KWDW_SCHEDOD) | KBDOSOUTPUT2/DWODSCH1.TXT | Pipe-delimited (SEP is assigned '\|'; this written payload uses :SEP:) | WRITE; WRITESEQ |
| [KWDW_SCHEDOD](../../kb-ultracs-datawarehouse/KWDW_SCHEDOD) | KBDOSOUTPUT2/DWODSCH2.TXT | Pipe-delimited (SEP is assigned '\|'; this written payload uses :SEP:) | WRITE; WRITESEQ |
| [KWDW_SCHEDOD](../../kb-ultracs-datawarehouse/KWDW_SCHEDOD) | KBDOSOUTPUT2/DWODSCH3.TXT | Other / format not determined (no delimiter or fixed-width evidence tied to this output) | WRITE |
| [KWDW_SECURITY](../../kb-ultracs-datawarehouse/KWDW_SECURITY) | KBDOSOUTPUT/DWLOG.TXT | Other / format not determined (no delimiter or fixed-width evidence tied to this output) | WRITE |
| [KWDW_SECURITY](../../kb-ultracs-datawarehouse/KWDW_SECURITY) | KBDOSOUTPUT/DWMTGDET.TXT | Pipe-delimited (SEP is assigned '\|'; this written payload uses :SEP:) | WRITE; WRITESEQ |
| [KWDW_SECURITY](../../kb-ultracs-datawarehouse/KWDW_SECURITY) | KBDOSOUTPUT/DWMTGIND.TXT | Other / format not determined (no delimiter or fixed-width evidence tied to this output) | WRITE; WRITESEQ |
| [KWDW_SECURITY](../../kb-ultracs-datawarehouse/KWDW_SECURITY) | KBDOSOUTPUT/DWSECIND.TXT | Other / format not determined (no delimiter or fixed-width evidence tied to this output) | WRITE; WRITESEQ |
| [KWDW_SECURITY](../../kb-ultracs-datawarehouse/KWDW_SECURITY) | KBDOSOUTPUT/DWSECUR.TXT | Pipe-delimited (SEP is assigned '\|'; this written payload uses :SEP:) | WRITE; WRITESEQ |
| [KWDW_SECURITY](../../kb-ultracs-datawarehouse/KWDW_SECURITY) | KBDOSOUTPUT/DWSECUR2.TXT | Pipe-delimited (SEP is assigned '\|'; this written payload uses :SEP:) | WRITE; WRITESEQ |
| [KWDW_SECURITY](../../kb-ultracs-datawarehouse/KWDW_SECURITY) | KBDOSOUTPUT/DWSECVAL.TXT | Pipe-delimited (SEP is assigned '\|'; this written payload uses :SEP:) | WRITE; WRITESEQ |
| [KWDW_SECURITY](../../kb-ultracs-datawarehouse/KWDW_SECURITY) | KBDOSOUTPUT2/DWLNINS2.TXT | Pipe-delimited (SEP is assigned '\|'; this written payload uses :SEP:) | WRITE; WRITESEQ |
| [KWDW_SRATES](../../kb-ultracs-datawarehouse/KWDW_SRATES) | KBDOSOUTPUT/DWLOG.TXT | Other / format not determined (no delimiter or fixed-width evidence tied to this output) | WRITE |
| [KWDW_SRATES](../../kb-ultracs-datawarehouse/KWDW_SRATES) | KBDOSOUTPUT/DWSRATES.TXT | Pipe-delimited (SEP is assigned '\|'; this written payload uses :SEP:) | WRITE; WRITESEQ |
| [KWDW_STML](../../kb-ultracs-datawarehouse/KWDW_STML) | KBDOSOUTPUT/DWLOG.TXT | Other / format not determined (no delimiter or fixed-width evidence tied to this output) | WRITE |
| [KWDW_STML](../../kb-ultracs-datawarehouse/KWDW_STML) | KBDOSOUTPUT2/DWEMAIL1.TXT | Pipe-delimited (SEP is assigned '\|'; this written payload uses :SEP:) | WRITE; WRITESEQ |
| [KWDW_STML](../../kb-ultracs-datawarehouse/KWDW_STML) | KBDOSOUTPUT2/DWEMAIL2.TXT | Pipe-delimited (SEP is assigned '\|'; this written payload uses :SEP:) | WRITE; WRITESEQ |
| [KWDW_STMT](../../kb-ultracs-datawarehouse/KWDW_STMT) | KBDOSOUTPUT/DWEDET.TXT | Pipe-delimited (SEP is assigned '\|'; this written payload uses :SEP:) | WRITE; WRITESEQ |
| [KWDW_STMT](../../kb-ultracs-datawarehouse/KWDW_STMT) | KBDOSOUTPUT/DWLOG.TXT | Other / format not determined (no delimiter or fixed-width evidence tied to this output) | WRITE |
| [KWDW_STMT](../../kb-ultracs-datawarehouse/KWDW_STMT) | KBDOSOUTPUT/KWSTATD.TXT | Pipe-delimited (SEP is assigned '\|'; this written payload uses :SEP:) | WRITE; WRITESEQ |
| [KWDW_SWEEP](../../kb-ultracs-datawarehouse/KWDW_SWEEP) | KBDOSOUTPUT/DWLOG.TXT | Other / format not determined (no delimiter or fixed-width evidence tied to this output) | WRITE |
| [KWDW_SWEEP](../../kb-ultracs-datawarehouse/KWDW_SWEEP) | KBDOSOUTPUT/DWSWEEP.TXT | Pipe-delimited (SEP is assigned '\|'; this written payload uses :SEP:) | WRITE; WRITESEQ |
| [KWDW_SWEEP](../../kb-ultracs-datawarehouse/KWDW_SWEEP) | KBDOSOUTPUT/DWSWEEPA.TXT | Other / format not determined (no delimiter or fixed-width evidence tied to this output) | WRITE |
| [KWDW_SWEEP](../../kb-ultracs-datawarehouse/KWDW_SWEEP) | KBDOSOUTPUT/DWSWEEPC.TXT | Pipe-delimited (SEP is assigned '\|'; this written payload uses :SEP:) | WRITE; WRITESEQ |
| [KWDW_SWEEPD](../../kb-ultracs-datawarehouse/KWDW_SWEEPD) | KBDOSOUTPUT/DWSWEEPD.TXT | Pipe-delimited (SEP is assigned '\|'; this written payload uses :SEP:) | WRITE; WRITESEQ |
| [KWDW_TDS](../../kb-ultracs-datawarehouse/KWDW_TDS) | KBDOSOUTPUT/DWLOG.TXT | Other / format not determined (no delimiter or fixed-width evidence tied to this output) | WRITE |
| [KWDW_TDS](../../kb-ultracs-datawarehouse/KWDW_TDS) | KBDOSOUTPUT/DWTDS.TXT | Pipe-delimited (SEP is assigned '\|'; this written payload uses :SEP:) | WRITE; WRITESEQ |
| [KWDW_TERM](../../kb-ultracs-datawarehouse/KWDW_TERM) | KBDOSOUTPUT/DWLOG.TXT | Other / format not determined (no delimiter or fixed-width evidence tied to this output) | WRITE |
| [KWDW_TERM](../../kb-ultracs-datawarehouse/KWDW_TERM) | KBDOSOUTPUT/DWOPERAT.TXT | Pipe-delimited (SEP is assigned '\|'; this written payload uses :SEP:) | WRITE; WRITESEQ |
| [KWDW_TERM](../../kb-ultracs-datawarehouse/KWDW_TERM) | KBDOSOUTPUT/DWTERMNO.TXT | Pipe-delimited (SEP is assigned '\|'; this written payload uses :SEP:) | WRITE; WRITESEQ |
| [KWDW_TERM](../../kb-ultracs-datawarehouse/KWDW_TERM) | KBDOSOUTPUT/KBOPSEC.TXT | Pipe-delimited (SEP is assigned '\|'; this written payload uses :SEP:) | WRITE; WRITESEQ |
| [KWDW_TERM](../../kb-ultracs-datawarehouse/KWDW_TERM) | KBDOSOUTPUT/KBPROGS.TXT | Pipe-delimited (SEP is assigned '\|'; this written payload uses :SEP:) | WRITE; WRITESEQ |
| [KWDW_TERM](../../kb-ultracs-datawarehouse/KWDW_TERM) | KBDOSOUTPUT/KBPROGSB.TXT | Pipe-delimited (SEP is assigned '\|'; this written payload uses :SEP:) | WRITE; WRITESEQ |
| [KWDW_TEXTRACT](../../kb-ultracs-datawarehouse/KWDW_TEXTRACT) | KBDOSOUTPUT3 | Pipe-delimited (SEP is assigned '\|'; this written payload uses :SEP:) | WRITESEQ |
| [KWDW_TEXTRACT](../../kb-ultracs-datawarehouse/KWDW_TEXTRACT) | KBDOSOUTPUT3/CTRL_TRAN.TXT | Other / format not determined (no delimiter or fixed-width evidence tied to this output) | WRITE |
| [KWDW_TEXTRACT](../../kb-ultracs-datawarehouse/KWDW_TEXTRACT) | KBDOSOUTPUT3/DWLOGT/.TXT | Other / format not determined (no delimiter or fixed-width evidence tied to this output) | WRITE |
| [KWDW_TEXTRACT](../../kb-ultracs-datawarehouse/KWDW_TEXTRACT) | KBDOSOUTPUT3/DYNAMIC(FNAME) | Other / format not determined (no delimiter or fixed-width evidence tied to this output) | WRITE |
| [KWDW_TEXTRACT](../../kb-ultracs-datawarehouse/KWDW_TEXTRACT) | KBDOSOUTPUT3/DYNAMIC(FNAMEBAL) | Other / format not determined (no delimiter or fixed-width evidence tied to this output) | WRITE |
| [KWDW_TEXTRACT](../../kb-ultracs-datawarehouse/KWDW_TEXTRACT) | KBDOSOUTPUT3/DYNAMIC(FNAMEDET) | Other / format not determined (no delimiter or fixed-width evidence tied to this output) | WRITE |
| [KWDW_TF](../../kb-ultracs-datawarehouse/KWDW_TF) | KBDOSOUTPUT/DWLOG.TXT | Other / format not determined (no delimiter or fixed-width evidence tied to this output) | WRITE |
| [KWDW_TF](../../kb-ultracs-datawarehouse/KWDW_TF) | KBDOSOUTPUT/DWSTMTFEES.CTL | Other / format not determined (no delimiter or fixed-width evidence tied to this output) | WRITE |
| [KWDW_TF](../../kb-ultracs-datawarehouse/KWDW_TF) | KBDOSOUTPUT/DWSTMTFEES.TXT | Pipe-delimited (SEP is assigned '\|'; this written payload uses :SEP:) | WRITE; WRITESEQ |
| [KWDW_TRANSDUMP](../../kb-ultracs-datawarehouse/KWDW_TRANSDUMP) | KBDOSOUTPUT/DWLOG.TXT | Other / format not determined (no delimiter or fixed-width evidence tied to this output) | WRITE |
| [KWDW_TRANSDUMP](../../kb-ultracs-datawarehouse/KWDW_TRANSDUMP) | KBDOSOUTPUT/DWTRNDUMP.TXT | Pipe-delimited (SEP is assigned '\|'; this written payload uses :SEP:) | WRITE; WRITESEQ |
| [KWTRNTAX](../../kb-ultracs-datawarehouse/KWTRNTAX) | KBDOSOUTPUT/DWLOG.TXT | Other / format not determined (no delimiter or fixed-width evidence tied to this output) | WRITE |
| [KWTRNTAX](../../kb-ultracs-datawarehouse/KWTRNTAX) | KBDOSOUTPUT/DWTRNTAX.TXT | Pipe-delimited (SEP is assigned '\|'; this written payload uses :SEP:) | WRITE; WRITESEQ |
| [KWTRNTAX](../../kb-ultracs-datawarehouse/KWTRNTAX) | KBDOSOUTPUT/DWTRNTAX/.LOG | Other / format not determined (no delimiter or fixed-width evidence tied to this output) | WRITE |
| [KWUTIL_ATMACTIVITY](../../kb-ultracs-datawarehouse/KWUTIL_ATMACTIVITY) | &HOLD& | Other / format not determined (no delimiter or fixed-width evidence tied to this output) | WRITESEQ |
| [KWUTIL_ATMLOGEXPORT](../../kb-ultracs-datawarehouse/KWUTIL_ATMLOGEXPORT) | &HOLD&/CARDJOURNAL.TXT | Pipe-delimited (SEP is assigned '\|'; this written payload uses :SEP:) | WRITESEQ |
| [KWUTIL_CDCACTIVITY](../../kb-ultracs-datawarehouse/KWUTIL_CDCACTIVITY) | &HOLD& | Other / format not determined (no delimiter or fixed-width evidence tied to this output) | WRITESEQ |
| [KWUTIL_DELETEPIE](../../kb-ultracs-datawarehouse/KWUTIL_DELETEPIE) | DYNAMIC(LOGDIR,LOGFILE) | Other / format not determined (no delimiter or fixed-width evidence tied to this output) | WRITESEQ |
| [KWUTIL_RBISESSION](../../kb-ultracs-datawarehouse/KWUTIL_RBISESSION) | &HOLD&/RBISESSION_{HEAD} | Pipe-delimited (SEP is assigned '\|'; this written payload uses :SEP:) | WRITE; WRITESEQ |
| [KWUTIL_REMOVEOFFSET](../../kb-ultracs-datawarehouse/KWUTIL_REMOVEOFFSET) | DYNAMIC(LOGDIR,LOGFILE) | Other / format not determined (no delimiter or fixed-width evidence tied to this output) | WRITESEQ |
