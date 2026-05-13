; ═══════════════════════════════════════════════════════════════════
; NEXUS — Windows Installer (NSIS)
;
; Installateur professionnel pour NEXUS Agent IA Souverain
; Utilise Modern UI 2, multi-langue (Français/English)
;
; Prérequis : NSIS 3.09+ (https://nsis.sourceforge.io/)
; Build : makensis installer\setup.nsi
; ═══════════════════════════════════════════════════════════════════

!define PRODUCT_NAME "NEXUS"
!define PRODUCT_VERSION "0.1.0"
!define PRODUCT_PUBLISHER "NEXUS AI"
!define PRODUCT_WEB_SITE "https://github.com/nexus-ai/nexus"
!define PRODUCT_DIR_REGKEY "Software\Microsoft\Windows\CurrentVersion\App Paths\NEXUS.exe"
!define PRODUCT_UNINST_KEY "Software\Microsoft\Windows\CurrentVersion\Uninstall\${PRODUCT_NAME}"
!define PRODUCT_UNINST_ROOT_KEY "HKLM"

; ── MUI Settings ────────────────────────────────────────────────
!include "MUI2.nsh"
!include "FileFunc.nsh"
!include "LogicLib.nsh"

!define MUI_ABORTWARNING
!define MUI_ICON "nexus\desktop\nexus_icon.ico"
!define MUI_UNICON "nexus\desktop\nexus_icon.ico"
!define MUI_WELCOMEFINISHPAGE_BITMAP "installer\welcome.bmp"
!define MUI_HEADERIMAGE
!define MUI_HEADERIMAGE_BITMAP "installer\header.bmp"
!define MUI_HEADERIMAGE_RIGHT

; Langue
!insertmacro MUI_LANGUAGE "French"
!insertmacro MUI_LANGUAGE "English"

; Pages
!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_LICENSE "LICENSE"
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES

; Page de fin avec option de lancement
!define MUI_FINISHPAGE_RUN "$INSTDIR\NEXUS.exe"
!define MUI_FINISHPAGE_RUN_TEXT "Lancer NEXUS maintenant"
!define MUI_FINISHPAGE_SHOWREADME "$INSTDIR\docs\GUIDE_INSTALLATION.md"
!define MUI_FINISHPAGE_SHOWREADME_TEXT "Lire le guide d'installation"
!define MUI_FINISHPAGE_LINK "Site web de NEXUS" "${PRODUCT_WEB_SITE}"
!define MUI_FINISHPAGE_LINK_TEXT "Visiter le site web"
!insertmacro MUI_PAGE_FINISH

; Pages de désinstallation
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES

; Informations sur l'installateur
Name "${PRODUCT_NAME} ${PRODUCT_VERSION}"
OutFile "dist\NEXUS-Setup-${PRODUCT_VERSION}.exe"
InstallDir "$PROGRAMFILES\${PRODUCT_NAME}"
InstallDirRegKey HKLM "${PRODUCT_DIR_REGKEY}" ""
ShowInstDetails show
ShowUnInstDetails show
RequestExecutionLevel admin

; ── Section d'installation ──────────────────────────────────────
Section "NEXUS" SecMain
  SetOutPath "$INSTDIR"
  SetOverwrite ifnewer

  ; Fichiers principaux
  File /r "dist\NEXUS.exe"
  File /r "nexus\"
  File "requirements.txt"
  File "pyproject.toml"
  File ".env.example"
  File "LICENSE"
  File "README.md"

  ; Documentation
  SetOutPath "$INSTDIR\docs"
  File /r "docs\"

  ; Scripts utilitaires
  SetOutPath "$INSTDIR"
  File "start_nexus.bat"
  File "start_web.bat"
  File "install_build.bat"

  ; Créer .env depuis .env.example
  IfFileExists "$INSTDIR\.env" +2 0
  CopyFiles "$INSTDIR\.env.example" "$INSTDIR\.env"

  ; Créer les raccourcis
  CreateDirectory "$SMPROGRAMS\${PRODUCT_NAME}"
  CreateShortCut "$SMPROGRAMS\${PRODUCT_NAME}\NEXUS.lnk" "$INSTDIR\NEXUS.exe"
  CreateShortCut "$SMPROGRAMS\${PRODUCT_NAME}\Guide d'installation.lnk" "$INSTDIR\docs\GUIDE_INSTALLATION.md"
  CreateShortCut "$SMPROGRAMS\${PRODUCT_NAME}\Desinstaller.lnk" "$INSTDIR\uninst.exe"
  CreateShortCut "$DESKTOP\NEXUS.lnk" "$INSTDIR\NEXUS.exe"

  ; Écrire les clés de registre
  WriteRegStr HKLM "${PRODUCT_DIR_REGKEY}" "" "$INSTDIR\NEXUS.exe"
  WriteRegStr HKLM "${PRODUCT_UNINST_KEY}" "DisplayName" "${PRODUCT_NAME}"
  WriteRegStr HKLM "${PRODUCT_UNINST_KEY}" "UninstallString" "$INSTDIR\uninst.exe"
  WriteRegStr HKLM "${PRODUCT_UNINST_KEY}" "DisplayVersion" "${PRODUCT_VERSION}"
  WriteRegStr HKLM "${PRODUCT_UNINST_KEY}" "URLInfoAbout" "${PRODUCT_WEB_SITE}"
  WriteRegStr HKLM "${PRODUCT_UNINST_KEY}" "Publisher" "${PRODUCT_PUBLISHER}"
  WriteRegStr HKLM "${PRODUCT_UNINST_KEY}" "DisplayIcon" "$INSTDIR\NEXUS.exe"
  WriteRegStr HKLM "${PRODUCT_UNINST_KEY}" "InstallLocation" "$INSTDIR"

  ; Taille de l'installation
  ${GetSize} "$INSTDIR" "/S=0K" $0
  IntFmt $0 "0x%08X" $0
  WriteRegDWORD HKLM "${PRODUCT_UNINST_KEY}" "EstimatedSize" "$0"

  ; Créer le désinstalleur
  WriteUninstaller "$INSTDIR\uninst.exe"
SectionEnd

; ── Section de désinstallation ──────────────────────────────────
Section Uninstall
  ; Supprimer les raccourcis
  Delete "$SMPROGRAMS\${PRODUCT_NAME}\NEXUS.lnk"
  Delete "$SMPROGRAMS\${PRODUCT_NAME}\Guide d'installation.lnk"
  Delete "$SMPROGRAMS\${PRODUCT_NAME}\Desinstaller.lnk"
  RMDir "$SMPROGRAMS\${PRODUCT_NAME}"
  Delete "$DESKTOP\NEXUS.lnk"

  ; Supprimer les fichiers
  Delete "$INSTDIR\NEXUS.exe"
  Delete "$INSTDIR\uninst.exe"
  Delete "$INSTDIR\requirements.txt"
  Delete "$INSTDIR\pyproject.toml"
  Delete "$INSTDIR\.env.example"
  Delete "$INSTDIR\LICENSE"
  Delete "$INSTDIR\README.md"
  Delete "$INSTDIR\start_nexus.bat"
  Delete "$INSTDIR\start_web.bat"
  Delete "$INSTDIR\install_build.bat"

  ; Supprimer les dossiers
  RMDir /r "$INSTDIR\nexus"
  RMDir /r "$INSTDIR\docs"
  RMDir /r "$INSTDIR\dist"

  ; Conserver .env et nexus_data (données utilisateur)
  ; L'utilisateur peut les supprimer manuellement s'il le souhaite

  ; Supprimer le dossier d'installation s'il est vide
  RMDir "$INSTDIR"

  ; Supprimer les clés de registre
  DeleteRegKey HKLM "${PRODUCT_UNINST_KEY}"
  DeleteRegKey HKLM "${PRODUCT_DIR_REGKEY}"
SectionEnd
