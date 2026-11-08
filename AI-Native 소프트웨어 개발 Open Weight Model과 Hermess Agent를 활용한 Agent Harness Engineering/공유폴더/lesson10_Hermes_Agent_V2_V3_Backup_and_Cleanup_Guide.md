# Hermes Agent Harness Engineering — v2·v3 백업 및 수업 환경 정리 가이드

> **환경:** Windows 11 · PowerShell · Docker Desktop · Docker Compose  
> **적용 대상:** `C:\AI-Native` 아래의 v2·v3 실습 환경  
> **목적:** 수업 산출물을 ZIP으로 보관한 다음 실습실 PC에서 수업용 Docker 자원과 Windows 작업 파일을 제거합니다.

## 1. 작업 개요

수업 종료 후 다음 순서로 진행합니다.

1. **백업:** v2·v3 관련 네 폴더를 하나의 ZIP 파일로 압축합니다.
2. **백업 보관:** 생성된 ZIP이 열리는지 확인하고, 필요한 경우 `C:\AI-Native` **외부** 저장장치 또는 안전한 보관 위치로 복사합니다.
3. **Docker 정리:** v2·v3 Docker Compose 프로젝트의 컨테이너·전용 볼륨·네트워크를 삭제합니다.
4. **파일 정리:** `C:\AI-Native` 폴더를 통째로 삭제합니다.
5. **최종 확인:** v2·v3 관련 Docker 자원과 작업 폴더가 남아 있지 않은지 확인합니다.

**중요:** 3~4단계는 되돌릴 수 없는 삭제 작업입니다. 백업을 보존하려면 ZIP을 반드시 `C:\AI-Native` 밖으로 옮긴 뒤 진행합니다. Docker의 다른 프로젝트나 공용 리소스를 삭제하지 않습니다.

## 2. 백업 대상 및 범위

| 폴더 | 주요 내용 |
|---|---|
| `C:\AI-Native\hermes-training-v2` | v2 Docker Compose 설정 및 관련 파일 |
| `C:\AI-Native\work-request-manager-v2` | v2 프로젝트 소스 및 실습 결과 |
| `C:\AI-Native\hermes-training-v3` | v3 Docker Compose 설정 및 관련 파일 |
| `C:\AI-Native\work-request-manager-v3` | v3 프로젝트 소스·명세·계획·테스트·Harness·증거 기록 |

아래 명령은 다시 설치할 수 있는 `node_modules`, `dist`, `.vite`, `.git` 하위 내용을 제외합니다. **Docker 볼륨의 내부 데이터(예: Hermes Chat 기록, 모델 설정)는 이 ZIP 백업에 포함되지 않습니다.** 또한 `.env`가 존재하면 ZIP에 포함될 수 있으므로 교육생에게 그대로 배포하지 말고 안전하게 보관합니다.

### STEP B1 — ZIP 백업 생성

PowerShell에서 다음 블록을 **전체 복사하여 한 번에 실행**합니다.

```powershell
& {
    $ErrorActionPreference = 'Stop'

    $root = 'C:\AI-Native'
    $backupDir = Join-Path $root 'backups'
    $folders = @(
        'hermes-training-v2',
        'work-request-manager-v2',
        'hermes-training-v3',
        'work-request-manager-v3'
    )

    Write-Host "`n=== v2 + v3 수업 자료 ZIP 백업 ===" -ForegroundColor Cyan

    foreach ($folder in $folders) {
        $path = Join-Path $root $folder
        if (-not (Test-Path -LiteralPath $path -PathType Container)) {
            throw "백업 대상 폴더 누락: $path"
        }
        Write-Host "[PASS] 대상 확인: $folder" -ForegroundColor Green
    }

    New-Item -ItemType Directory -Path $backupDir -Force | Out-Null
    $stamp = Get-Date -Format 'yyyyMMdd_HHmmss'
    $zip = Join-Path $backupDir "Hermes_Agent_Training_V2_V3_$stamp.zip"

    $tarArgs = @(
        '-a', '-c', '-f', $zip,
        '--exclude=*/node_modules/*',
        '--exclude=*/dist/*',
        '--exclude=*/.vite/*',
        '--exclude=*/.git/*',
        '-C', $root
    ) + $folders

    & tar.exe @tarArgs
    if ($LASTEXITCODE -ne 0) { throw 'ZIP 압축 실패' }
    if (-not (Test-Path -LiteralPath $zip -PathType Leaf)) {
        throw 'ZIP 파일이 생성되지 않았습니다.'
    }

    $entries = @(& tar.exe -tf $zip)
    if ($LASTEXITCODE -ne 0) { throw 'ZIP 내부 목록 조회 실패' }

    foreach ($folder in $folders) {
        $found = @($entries | Where-Object {
            $_ -eq "$folder/" -or $_ -like "$folder/*"
        })
        if ($found.Count -eq 0) { throw "ZIP 내부 항목 누락: $folder" }
        Write-Host "[PASS] ZIP 포함: $folder" -ForegroundColor Green
    }

    $file = Get-Item -LiteralPath $zip
    Write-Host "`n[PASS] ZIP 백업 생성 완료" -ForegroundColor Green
    Write-Host "위치: $($file.FullName)"
    Write-Host "크기: $([math]::Round($file.Length / 1MB, 2)) MB"
    Write-Host "항목 수: $($entries.Count)"
}
```

**정상 확인:** `ZIP 백업 생성 완료`와 네 폴더의 `[PASS] ZIP 포함`이 표시됩니다. 이 확인은 압축 파일의 구조를 검사하는 것이며, 애플리케이션 전체 복원 성공까지 보증하지는 않습니다.

### STEP B2 — ZIP 파일 외부 보관

백업 파일이 생성되는 기본 위치는 다음과 같습니다.

```text
C:\AI-Native\backups\Hermes_Agent_Training_V2_V3_YYYYMMDD_HHMMSS.zip
```

실습실 PC에서 `C:\AI-Native`를 삭제할 예정이므로, **이 ZIP을 외장 드라이브나 다른 안전한 위치로 복사한 뒤 파일 크기와 열림 여부를 확인**합니다. 기밀 정보가 들어 있을 수 있으므로 접근 권한이 제한된 장소에 보관합니다. 백업이 필요 없다면 이 단계는 생략할 수 있지만, 삭제 이후에는 해당 프로젝트를 복구할 수 없습니다.

## 3. 수업용 Docker 자원 삭제

### STEP D1 — v2·v3 Compose 컨테이너·볼륨·네트워크 삭제

아래 명령은 **v2와 v3 두 Compose 프로젝트만** 대상으로 합니다. 각 프로젝트의 `name` 값을 확인한 뒤 삭제합니다. `down -v`는 해당 Compose 프로젝트가 관리하는 전용 볼륨의 데이터를 삭제하므로, **Hermes Agent의 Docker 볼륨 내부 채팅·설정도 함께 없어질 수 있습니다.**

```powershell
& {
    $ErrorActionPreference = 'Stop'

    foreach ($name in @('hermes-training-v2', 'hermes-training-v3')) {
        $path = "C:\AI-Native\$name"
        if (-not (Test-Path -LiteralPath $path -PathType Container)) {
            throw "Compose 폴더 없음: $path"
        }

        Set-Location -LiteralPath $path
        $configText = docker compose config --format json
        if ($LASTEXITCODE -ne 0) { throw "Compose 설정 조회 실패: $name" }
        $config = $configText | ConvertFrom-Json
        if ($config.name -ne $name) {
            throw "Compose 프로젝트 확인 실패: $name"
        }

        docker compose down -v --remove-orphans
        if ($LASTEXITCODE -ne 0) {
            throw "Docker 자원 삭제 실패: $name"
        }

        Write-Host "[PASS] $name Docker 자원 삭제" -ForegroundColor Green
    }
}
```

**정상 확인:** 각 프로젝트에 대해 `[PASS] hermes-training-v2 Docker 자원 삭제` 및 `[PASS] hermes-training-v3 Docker 자원 삭제`가 표시됩니다. Docker Desktop 자체와 다른 Compose 프로젝트는 그대로 둡니다.

## 4. Windows 수업 파일 전체 삭제

### STEP D2 — `C:\AI-Native` 삭제

**D1 성공 후에만** 실행합니다. PowerShell의 작업 위치가 삭제 대상 내부에 있을 수 있으므로 `C:\`로 이동합니다.

> **경고:** `C:\AI-Native`에 포함된 모든 파일과 `backups` 폴더도 함께 삭제됩니다. ZIP 보관 여부를 반드시 먼저 확인합니다.

```powershell
& {
    $ErrorActionPreference = 'Stop'

    $target = 'C:\AI-Native'
    Set-Location -LiteralPath 'C:\'

    Write-Host "`n=== AI-Native 수업 폴더 전체 삭제 ===" -ForegroundColor Cyan

    if (Test-Path -LiteralPath $target -PathType Container) {
        Remove-Item -LiteralPath $target -Recurse -Force -ErrorAction Stop
    }

    if (Test-Path -LiteralPath $target) {
        throw 'AI-Native 폴더 삭제 실패'
    }

    Write-Host '[PASS] C:\AI-Native 삭제 완료' -ForegroundColor Green
}
```

**정상 확인:** `[PASS] C:\AI-Native 삭제 완료`가 표시되고 PowerShell 프롬프트가 `PS C:\>`로 돌아옵니다.

## 5. 최종 잔여 자원 점검

### STEP D3 — 삭제 없이 확인만 수행

아래 명령은 Docker 컨테이너·볼륨·네트워크 이름과 작업 폴더의 존재 여부를 **조회만** 합니다.

```powershell
& {
    $ErrorActionPreference = 'Stop'

    Write-Host "`n=== Hermes v2/v3 잔여 자원 확인 ===" -ForegroundColor Cyan
    $remaining = @()

    $containers = @(docker ps -a --format '{{.Names}}')
    if ($LASTEXITCODE -ne 0) { throw '컨테이너 조회 실패' }

    $volumes = @(docker volume ls --format '{{.Name}}')
    if ($LASTEXITCODE -ne 0) { throw '볼륨 조회 실패' }

    $networks = @(docker network ls --format '{{.Name}}')
    if ($LASTEXITCODE -ne 0) { throw '네트워크 조회 실패' }

    $remaining += @($containers | Where-Object { $_ -match '^hermes-training-v[23][-_]' })
    $remaining += @($volumes    | Where-Object { $_ -match '^hermes-training-v[23][-_]' })
    $remaining += @($networks   | Where-Object { $_ -match '^hermes-training-v[23][-_]' })

    if (Test-Path -LiteralPath 'C:\AI-Native') {
        $remaining += 'C:\AI-Native'
    }

    if ($remaining.Count -eq 0) {
        Write-Host '[PASS] v2/v3 잔여 Docker 자원 없음' -ForegroundColor Green
        Write-Host '[PASS] C:\AI-Native 폴더 없음' -ForegroundColor Green
    }
    else {
        Write-Host '[CHECK] 잔여 항목 발견:' -ForegroundColor Yellow
        $remaining | ForEach-Object { Write-Host $_ }
    }
}
```

**정상 확인:** 다음 두 줄이 표시됩니다.

```text
[PASS] v2/v3 잔여 Docker 자원 없음
[PASS] C:\AI-Native 폴더 없음
```

## 6. 실습실 보안 및 운영 주의사항

- **API Key 폐기:** 교육생이 만든 OpenRouter API Key는 서비스 계정에서 별도로 폐기합니다. 파일 삭제만으로 유출된 키의 사용을 차단할 수는 없습니다.
- **브라우저·PowerShell 기록:** 저장된 로그인 정보, 다운로드 파일, 명령 기록에 인증 정보가 남았는지 확인합니다.
- **별도 설치:** Windows 사용자 프로필에 설치된 Hermes Agent나 다른 폴더의 자료는 이 가이드의 삭제 대상이 아닙니다.
- **Docker 외부 데이터:** 외부 볼륨, 별도 bind mount 및 Compose 외부에서 만든 리소스는 이름 기반 잔여 검사로 모두 탐지되지 않을 수 있습니다.
- **삭제와 보안 소거는 다름:** `Remove-Item`은 일반 파일 삭제이며, SSD에 남은 데이터의 물리적 복구 불가능성을 보장하지 않습니다. 공용 PC의 전체 초기화는 기관의 사용자 프로필·PC 복원 정책을 따릅니다.

## 7. 수업 종료 체크리스트

- [ ] ZIP 파일 생성 및 내부 네 폴더 확인 (백업이 필요한 경우)
- [ ] 백업 ZIP을 `C:\AI-Native` 외부로 이동 및 확인
- [ ] v2 Compose `down -v --remove-orphans` 성공
- [ ] v3 Compose `down -v --remove-orphans` 성공
- [ ] `C:\AI-Native` 전체 삭제 성공
- [ ] v2·v3 Docker 잔여 자원 없음 확인
- [ ] API Key 및 사용자 로그인 정보 별도 정리

---

**운영 참고:** 본 가이드에 포함된 Docker 삭제·폴더 삭제·잔여 자원 확인 절차는 실제 수업 종료 시 PowerShell에서 PASS 출력을 확인한 순서에 맞추어 정리했습니다. ZIP 생성 절차는 동일 환경에서 사용하도록 제시한 백업 명령이며, 이 대화에서는 해당 ZIP의 생성 완료 출력이 제공되지 않았으므로 백업 성공 여부를 별도로 확인해야 합니다.
