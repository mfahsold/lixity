; Tauri v2 NSIS lifecycle hooks for Lixity Desktop (Windows).
; User manuscript folders, research archives and %LOCALAPPDATA%\lixity state are
; deliberately preserved across upgrades and uninstalls.

!macro NSIS_HOOK_POSTINSTALL
  DetailPrint "Lixity Desktop installed. User manuscripts and research archives stay untouched."
!macroend

!macro NSIS_HOOK_PREUNINSTALL
  DetailPrint "Removing Lixity Desktop program files only; keeping user manuscripts and project state."
!macroend
