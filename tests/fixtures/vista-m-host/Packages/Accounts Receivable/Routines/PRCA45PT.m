PRCA45PT ;ALB/CMS - PURGE EXEMPT BILL FILES ;6/30/97  09:13
 ;;4.5;Accounts Receivable;**14,79,153,302,409**;Mar 20, 1995;Build 78
 ;Per VHA Directive 2004-038, this routine should not be modified.
V ; version stub
 Q
EN ; entry
 D BMES^XPDUTL("Purging exempt bills")
 Q
430 ; iterate file 430
 Q
433 ; iterate file 433
 Q
XCLN ; cleanup
 Q
