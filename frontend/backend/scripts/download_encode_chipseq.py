#!/usr/bin/env python3
"""
Download ENCODE histone modification ChIP-seq data from UCSC.

This script downloads broadPeak files from the Broad Histone track
for multiple cell lines and histone marks.

Usage:
    python3 download_encode_chipseq.py --all --output encode_data/
    python3 download_encode_chipseq.py --mark H3K27me3 --cell-line GM12878
"""

import argparse
import subprocess
from pathlib import Path
from typing import List, Optional
import json
import gzip


# UCSC ENCODE Histone base URLs (hg19)
BASE_URL_BROAD = 'http://hgdownload.soe.ucsc.edu/goldenPath/hg19/encodeDCC/wgEncodeBroadHistone/'
BASE_URL_UW = 'http://hgdownload.soe.ucsc.edu/goldenPath/hg19/encodeDCC/wgEncodeUwHistone/'
BASE_URL_SYDH = 'http://hgdownload.soe.ucsc.edu/goldenPath/hg19/encodeDCC/wgEncodeSydhHistone/'
# Legacy URL (kept for backward compatibility)
BASE_URL = BASE_URL_BROAD

# File naming pattern: wgEncodeBroadHistone{CellLine}{Mark}{Replicate}.broadPeak.gz
# Example: wgEncodeBroadHistoneGm12878H3k27me3StdPk.broadPeak.gz

ENCODE_FILES = {
    'A549': {
        # A549 在 UCSC hg19 BroadHistone 中主要是处理组（例如 Etoh02 / Dex100nm），没有 StdPk。
        # 为了和当前数据库中的 A549 experiments 对齐，这里选择 Etoh02 版本。
        'H3K27me3': {
            'file': 'wgEncodeBroadHistoneA549H3k27me3Etoh02Pk.broadPeak.gz',
            'url': BASE_URL_BROAD + 'wgEncodeBroadHistoneA549H3k27me3Etoh02Pk.broadPeak.gz',
            'size_mb': None,
            'treatment': 'Etoh02',
        },
        'H3K4me1': {
            # 注意：UCSC 使用 H3k04me1（带 0），不是 H3k4me1
            'file': 'wgEncodeBroadHistoneA549H3k04me1Etoh02Pk.broadPeak.gz',
            'url': BASE_URL_BROAD + 'wgEncodeBroadHistoneA549H3k04me1Etoh02Pk.broadPeak.gz',
            'size_mb': None,
            'treatment': 'Etoh02',
        },
        'H3K4me2': {
            # 注意：UCSC 使用 H3k04me2（带 0）
            'file': 'wgEncodeBroadHistoneA549H3k04me2Etoh02Pk.broadPeak.gz',
            'url': BASE_URL_BROAD + 'wgEncodeBroadHistoneA549H3k04me2Etoh02Pk.broadPeak.gz',
            'size_mb': None,
            'treatment': 'Etoh02',
        },
        'H3K4me3': {
            # 注意：UCSC 使用 H3k04me3（带 0）
            'file': 'wgEncodeBroadHistoneA549H3k04me3Etoh02Pk.broadPeak.gz',
            'url': BASE_URL_BROAD + 'wgEncodeBroadHistoneA549H3k04me3Etoh02Pk.broadPeak.gz',
            'size_mb': None,
            'treatment': 'Etoh02',
        },
        'H3K27ac': {
            'file': 'wgEncodeBroadHistoneA549H3k27acEtoh02Pk.broadPeak.gz',
            'url': BASE_URL_BROAD + 'wgEncodeBroadHistoneA549H3k27acEtoh02Pk.broadPeak.gz',
            'size_mb': None,
            'treatment': 'Etoh02',
        },
        'H3K36me3': {
            'file': 'wgEncodeBroadHistoneA549H3k36me3Etoh02Pk.broadPeak.gz',
            'url': BASE_URL_BROAD + 'wgEncodeBroadHistoneA549H3k36me3Etoh02Pk.broadPeak.gz',
            'size_mb': None,
            'treatment': 'Etoh02',
        },
        'H3K9ac': {
            # 注意：UCSC 使用 H3k09ac（带 0），不是 H3k9ac
            'file': 'wgEncodeBroadHistoneA549H3k09acEtoh02Pk.broadPeak.gz',
            'url': BASE_URL_BROAD + 'wgEncodeBroadHistoneA549H3k09acEtoh02Pk.broadPeak.gz',
            'size_mb': None,
            'treatment': 'Etoh02',
        },
        'H3K9me3': {
            # 注意：UCSC 使用 H3k09me3（带 0），不是 H3k9me3
            'file': 'wgEncodeBroadHistoneA549H3k09me3Etoh02Pk.broadPeak.gz',
            'url': BASE_URL_BROAD + 'wgEncodeBroadHistoneA549H3k09me3Etoh02Pk.broadPeak.gz',
            'size_mb': None,
            'treatment': 'Etoh02',
        },
    },
    'GM12878': {
        'H3K27me3': {
            'file': 'wgEncodeBroadHistoneGm12878H3k27me3StdPk.broadPeak.gz',
            'url': BASE_URL + 'wgEncodeBroadHistoneGm12878H3k27me3StdPk.broadPeak.gz',
            'size_mb': 2.1,
        },
        'H3K4me1': {
            'file': 'wgEncodeBroadHistoneGm12878H3k4me1StdPk.broadPeak.gz',
            'url': BASE_URL + 'wgEncodeBroadHistoneGm12878H3k4me1StdPk.broadPeak.gz',
            'size_mb': 5.1,
        },
        'H3K4me3': {
            'file': 'wgEncodeBroadHistoneGm12878H3k4me3StdPk.broadPeak.gz',
            'url': BASE_URL + 'wgEncodeBroadHistoneGm12878H3k4me3StdPk.broadPeak.gz',
            'size_mb': 1.8,
        },
        'H3K27ac': {
            'file': 'wgEncodeBroadHistoneGm12878H3k27acStdPk.broadPeak.gz',
            'url': BASE_URL + 'wgEncodeBroadHistoneGm12878H3k27acStdPk.broadPeak.gz',
            'size_mb': 4.5,
        },
        'H3K36me3': {
            'file': 'wgEncodeBroadHistoneGm12878H3k36me3StdPk.broadPeak.gz',
            'url': BASE_URL + 'wgEncodeBroadHistoneGm12878H3k36me3StdPk.broadPeak.gz',
            'size_mb': 0.5,
        },
        'H3K9me3': {
            'file': 'wgEncodeBroadHistoneGm12878H3k9me3StdPk.broadPeak.gz',
            'url': BASE_URL + 'wgEncodeBroadHistoneGm12878H3k9me3StdPk.broadPeak.gz',
            'size_mb': 1.1,
        },
        # Phase 5 新增 marks
        'H3K9ac': {
            'file': 'wgEncodeBroadHistoneGm12878H3k9acStdPk.broadPeak.gz',
            'url': BASE_URL + 'wgEncodeBroadHistoneGm12878H3k9acStdPk.broadPeak.gz',
            'size_mb': 3.0,
        },
        'H3K4me2': {
            'file': 'wgEncodeBroadHistoneGm12878H3k4me2StdPk.broadPeak.gz',
            'url': BASE_URL + 'wgEncodeBroadHistoneGm12878H3k4me2StdPk.broadPeak.gz',
            'size_mb': 4.0,
        },
    },
    'H1-hESC': {
        'H3K27me3': {
            'file': 'wgEncodeBroadHistoneH1hescH3k27me3StdPk.broadPeak.gz',
            'url': BASE_URL + 'wgEncodeBroadHistoneH1hescH3k27me3StdPk.broadPeak.gz',
            'size_mb': 1.5,
        },
        'H3K4me1': {
            'file': 'wgEncodeBroadHistoneH1hescH3k4me1StdPk.broadPeak.gz',
            'url': BASE_URL + 'wgEncodeBroadHistoneH1hescH3k4me1StdPk.broadPeak.gz',
            'size_mb': 4.2,
        },
        'H3K4me3': {
            'file': 'wgEncodeBroadHistoneH1hescH3k4me3StdPk.broadPeak.gz',
            'url': BASE_URL + 'wgEncodeBroadHistoneH1hescH3k4me3StdPk.broadPeak.gz',
            'size_mb': 1.2,
        },
        'H3K27ac': {
            'file': 'wgEncodeBroadHistoneH1hescH3k27acStdPk.broadPeak.gz',
            'url': BASE_URL + 'wgEncodeBroadHistoneH1hescH3k27acStdPk.broadPeak.gz',
            'size_mb': 3.8,
        },
        'H3K36me3': {
            'file': 'wgEncodeBroadHistoneH1hescH3k36me3StdPk.broadPeak.gz',
            'url': BASE_URL + 'wgEncodeBroadHistoneH1hescH3k36me3StdPk.broadPeak.gz',
            'size_mb': 0.6,
        },
        'H3K9me3': {
            # 注意：UCSC 使用 H3k09me3（带 0），不是 H3k9me3
            'file': 'wgEncodeBroadHistoneH1hescH3k09me3StdPk.broadPeak.gz',
            'url': BASE_URL + 'wgEncodeBroadHistoneH1hescH3k09me3StdPk.broadPeak.gz',
            'size_mb': 1.3,
        },
        # Phase 5 新增 marks
        'H3K9ac': {
            'file': 'wgEncodeBroadHistoneH1hescH3k9acStdPk.broadPeak.gz',
            'url': BASE_URL + 'wgEncodeBroadHistoneH1hescH3k9acStdPk.broadPeak.gz',
            'size_mb': 2.5,
        },
        'H3K4me2': {
            'file': 'wgEncodeBroadHistoneH1hescH3k4me2StdPk.broadPeak.gz',
            'url': BASE_URL + 'wgEncodeBroadHistoneH1hescH3k4me2StdPk.broadPeak.gz',
            'size_mb': 3.5,
        },
    },
    'K562': {
        'H3K27me3': {
            'file': 'wgEncodeBroadHistoneK562H3k27me3StdPk.broadPeak.gz',
            'url': BASE_URL + 'wgEncodeBroadHistoneK562H3k27me3StdPk.broadPeak.gz',
            'size_mb': 2.3,
        },
        'H3K4me1': {
            'file': 'wgEncodeBroadHistoneK562H3k4me1StdPk.broadPeak.gz',
            'url': BASE_URL + 'wgEncodeBroadHistoneK562H3k4me1StdPk.broadPeak.gz',
            'size_mb': 4.8,
        },
        'H3K4me3': {
            'file': 'wgEncodeBroadHistoneK562H3k4me3StdPk.broadPeak.gz',
            'url': BASE_URL + 'wgEncodeBroadHistoneK562H3k4me3StdPk.broadPeak.gz',
            'size_mb': 1.6,
        },
        'H3K27ac': {
            'file': 'wgEncodeBroadHistoneK562H3k27acStdPk.broadPeak.gz',
            'url': BASE_URL + 'wgEncodeBroadHistoneK562H3k27acStdPk.broadPeak.gz',
            'size_mb': 4.2,
        },
        'H3K36me3': {
            'file': 'wgEncodeBroadHistoneK562H3k36me3StdPk.broadPeak.gz',
            'url': BASE_URL + 'wgEncodeBroadHistoneK562H3k36me3StdPk.broadPeak.gz',
            'size_mb': 0.8,
        },
        'H3K9me3': {
            'file': 'wgEncodeBroadHistoneK562H3k9me3StdPk.broadPeak.gz',
            'url': BASE_URL + 'wgEncodeBroadHistoneK562H3k9me3StdPk.broadPeak.gz',
            'size_mb': 0.7,
        },
        # Phase 5 新增 marks（UCSC hg19/Broad Histone 也可用）
        'H3K9ac': {
            'file': 'wgEncodeBroadHistoneK562H3k9acStdPk.broadPeak.gz',
            'url': BASE_URL + 'wgEncodeBroadHistoneK562H3k9acStdPk.broadPeak.gz',
            'size_mb': 0.8,
        },
        'H3K4me2': {
            'file': 'wgEncodeBroadHistoneK562H3k4me2StdPk.broadPeak.gz',
            'url': BASE_URL + 'wgEncodeBroadHistoneK562H3k4me2StdPk.broadPeak.gz',
            'size_mb': 1.1,
        },
    },
    'HepG2': {
        'H3K27me3': {
            'file': 'wgEncodeBroadHistoneHepg2H3k27me3StdPk.broadPeak.gz',
            'url': BASE_URL_BROAD + 'wgEncodeBroadHistoneHepg2H3k27me3StdPk.broadPeak.gz',
            'size_mb': 1.2,
        },
        'H3K4me1': {
            # 注意：UCSC 使用 H3k04me1（带 0），不是 H3k4me1
            'file': 'wgEncodeBroadHistoneHepg2H3k04me1StdPk.broadPeak.gz',
            'url': BASE_URL_BROAD + 'wgEncodeBroadHistoneHepg2H3k04me1StdPk.broadPeak.gz',
            'size_mb': 2.1,
        },
        'H3K4me3': {
            'file': 'wgEncodeBroadHistoneHepg2H3k4me3StdPk.broadPeak.gz',
            'url': BASE_URL_BROAD + 'wgEncodeBroadHistoneHepg2H3k4me3StdPk.broadPeak.gz',
            'size_mb': 0.8,
        },
        'H3K27ac': {
            'file': 'wgEncodeBroadHistoneHepg2H3k27acStdPk.broadPeak.gz',
            'url': BASE_URL_BROAD + 'wgEncodeBroadHistoneHepg2H3k27acStdPk.broadPeak.gz',
            'size_mb': 0.7,
        },
        'H3K36me3': {
            'file': 'wgEncodeBroadHistoneHepg2H3k36me3StdPk.broadPeak.gz',
            'url': BASE_URL_BROAD + 'wgEncodeBroadHistoneHepg2H3k36me3StdPk.broadPeak.gz',
            'size_mb': 0.6,
        },
        'H3K9me3': {
            # 注意：UCSC HepG2 的 H3K9me3 文件是 Pk（无 Std），且为 H3k09me3（带 0）
            'file': 'wgEncodeBroadHistoneHepg2H3k09me3Pk.broadPeak.gz',
            'url': BASE_URL_BROAD + 'wgEncodeBroadHistoneHepg2H3k09me3Pk.broadPeak.gz',
            'size_mb': 0.8,
        },
        'H3K9ac': {
            'file': 'wgEncodeBroadHistoneHepg2H3k9acStdPk.broadPeak.gz',
            'url': BASE_URL_BROAD + 'wgEncodeBroadHistoneHepg2H3k9acStdPk.broadPeak.gz',
            'size_mb': 0.8,
        },
        'H3K4me2': {
            'file': 'wgEncodeBroadHistoneHepg2H3k4me2StdPk.broadPeak.gz',
            'url': BASE_URL_BROAD + 'wgEncodeBroadHistoneHepg2H3k4me2StdPk.broadPeak.gz',
            'size_mb': 1.3,
        },
    },
    # MCF-7: Breast adenocarcinoma cell line
    # - UW Histone: H3K4me3
    # - Sydh Histone: subset of marks available as narrowPeak (PeakSeq)
    'MCF-7': {
        'H3K4me3': {
            'file': 'wgEncodeUwHistoneMcf7H3k4me3StdHotspotsRep1.broadPeak.gz',
            'url': BASE_URL_UW + 'wgEncodeUwHistoneMcf7H3k4me3StdHotspotsRep1.broadPeak.gz',
            'size_mb': 0.5,
        },
        'H3K27ac': {
            'file': 'wgEncodeSydhHistoneMcf7H3k27acUcdPk.narrowPeak.gz',
            'url': BASE_URL_SYDH + 'wgEncodeSydhHistoneMcf7H3k27acUcdPk.narrowPeak.gz',
            'size_mb': 0.5,
            'peak_type': 'narrow',
        },
        'H3K9me3': {
            # 注意：UCSC 使用 H3k09me3（带 0），不是 H3k9me3
            'file': 'wgEncodeSydhHistoneMcf7H3k09me3UcdPk.narrowPeak.gz',
            'url': BASE_URL_SYDH + 'wgEncodeSydhHistoneMcf7H3k09me3UcdPk.narrowPeak.gz',
            'size_mb': 0.2,
            'peak_type': 'narrow',
        },
        'H3K27me3': {
            # 注意：UCSC Sydh track 使用 H3k27me3b（H3K27me3 抗体版本标记）
            'file': 'wgEncodeSydhHistoneMcf7H3k27me3bUcdPk.narrowPeak.gz',
            'url': BASE_URL_SYDH + 'wgEncodeSydhHistoneMcf7H3k27me3bUcdPk.narrowPeak.gz',
            'size_mb': 0.4,
            'peak_type': 'narrow',
        },
        'H3K36me3': {
            # 注意：UCSC Sydh track 使用 H3k36me3b（H3K36me3 抗体版本标记）
            'file': 'wgEncodeSydhHistoneMcf7H3k36me3bUcdPk.narrowPeak.gz',
            'url': BASE_URL_SYDH + 'wgEncodeSydhHistoneMcf7H3k36me3bUcdPk.narrowPeak.gz',
            'size_mb': 0.9,
            'peak_type': 'narrow',
        },
    },
    # HMEC: Human mammary epithelial cells (Broad Histone track - full data)
    'HMEC': {
        'H3K4me1': {
            'file': 'wgEncodeBroadHistoneHmecH3k4me1StdPk.broadPeak.gz',
            'url': BASE_URL_BROAD + 'wgEncodeBroadHistoneHmecH3k4me1StdPk.broadPeak.gz',
            'size_mb': 5.0,
        },
        # Phase 5 新增 marks（补齐 8 marks 覆盖）
        'H3K4me2': {
            'file': 'wgEncodeBroadHistoneHmecH3k4me2StdPk.broadPeak.gz',
            'url': BASE_URL_BROAD + 'wgEncodeBroadHistoneHmecH3k4me2StdPk.broadPeak.gz',
            'size_mb': 1.6,
        },
        'H3K4me3': {
            'file': 'wgEncodeBroadHistoneHmecH3k4me3StdPk.broadPeak.gz',
            'url': BASE_URL_BROAD + 'wgEncodeBroadHistoneHmecH3k4me3StdPk.broadPeak.gz',
            'size_mb': 1.5,
        },
        'H3K9me3': {
            'file': 'wgEncodeBroadHistoneHmecH3k09me3Pk.broadPeak.gz',
            'url': BASE_URL_BROAD + 'wgEncodeBroadHistoneHmecH3k09me3Pk.broadPeak.gz',
            'size_mb': 2.0,
        },
        # Phase 5 新增 marks（补齐 8 marks 覆盖）
        'H3K9ac': {
            'file': 'wgEncodeBroadHistoneHmecH3k9acStdPk.broadPeak.gz',
            'url': BASE_URL_BROAD + 'wgEncodeBroadHistoneHmecH3k9acStdPk.broadPeak.gz',
            'size_mb': 0.9,
        },
        'H3K27me3': {
            'file': 'wgEncodeBroadHistoneHmecH3k27me3StdPk.broadPeak.gz',
            'url': BASE_URL_BROAD + 'wgEncodeBroadHistoneHmecH3k27me3StdPk.broadPeak.gz',
            'size_mb': 2.5,
        },
        'H3K27ac': {
            'file': 'wgEncodeBroadHistoneHmecH3k27acStdPk.broadPeak.gz',
            'url': BASE_URL_BROAD + 'wgEncodeBroadHistoneHmecH3k27acStdPk.broadPeak.gz',
            'size_mb': 4.0,
        },
        'H3K36me3': {
            'file': 'wgEncodeBroadHistoneHmecH3k36me3StdPk.broadPeak.gz',
            'url': BASE_URL_BROAD + 'wgEncodeBroadHistoneHmecH3k36me3StdPk.broadPeak.gz',
            'size_mb': 3.0,
        },
    },
}

# Metadata for each cell line
CELL_LINE_METADATA = {
    'A549': {
        'tissue_type': 'lung',
        'cell_type': 'lung_adenocarcinoma',
        'description': 'Lung carcinoma cell line',
        'category': 'cancer',
    },
    'GM12878': {
        'tissue_type': 'blood',
        'cell_type': 'B-lymphocyte',
        'description': 'B-lymphoblastoid cell line',
        'category': 'normal',
    },
    'H1-hESC': {
        'tissue_type': 'embryonic_stem_cell',
        'cell_type': 'embryonic_stem_cell',
        'description': 'Human embryonic stem cells',
        'category': 'stem_cell',
    },
    'K562': {
        'tissue_type': 'blood',
        'cell_type': 'erythroleukemia',
        'description': 'Chronic myelogenous leukemia',
        'category': 'cancer',
    },
    'HepG2': {
        'tissue_type': 'liver',
        'cell_type': 'hepatocellular_carcinoma',
        'description': 'Hepatocellular carcinoma cell line',
        'category': 'cancer',
    },
    'MCF-7': {
        'tissue_type': 'breast',
        'cell_type': 'breast_adenocarcinoma',
        'description': 'Breast adenocarcinoma cell line',
        'category': 'cancer',
    },
    'HMEC': {
        'tissue_type': 'breast',
        'cell_type': 'mammary_epithelial',
        'description': 'Human mammary epithelial cells',
        'category': 'normal',
    },
}


def _validate_downloaded_peak_file(path: Path, *, max_records_to_check: int = 5) -> tuple[bool, str]:
    """Sanity-check the downloaded broadPeak/narrowPeak file.

    Guardrails:
    - Catch HTML/404 pages mistakenly saved as .gz
    - Catch truncated/invalid gzip
    - Catch obviously wrong TSV format
    """
    try:
        size = path.stat().st_size
    except OSError as e:
        return False, f"stat_failed: {e}"

    if size <= 0:
        return False, "empty_file"

    def _validate_lines(fh) -> tuple[bool, str]:
        checked = 0
        for lineno, line in enumerate(fh, 1):
            stripped = line.strip()
            if not stripped:
                continue
            if stripped.startswith("#"):
                continue
            if stripped.startswith("track") or stripped.startswith("browser"):
                continue

            parts = stripped.split("\t")
            if len(parts) < 3:
                return False, f"too_few_columns: line={lineno}"
            try:
                int(parts[1])
                int(parts[2])
            except ValueError:
                return False, f"invalid_coords: line={lineno}"

            checked += 1
            if checked >= max_records_to_check:
                break

        if checked == 0:
            return False, "no_records"
        return True, "ok"

    if path.suffix == ".gz":
        try:
            with gzip.open(path, "rt", encoding="utf-8", errors="replace") as fh:
                return _validate_lines(fh)
        except OSError as e:
            # e.g. "Not a gzipped file" (HTML error page)
            return False, f"gzip_open_failed: {e}"

    try:
        with path.open("r", encoding="utf-8", errors="replace") as fh:
            return _validate_lines(fh)
    except OSError as e:
        return False, f"open_failed: {e}"


def download_file(url: str, output_path: Path, *, dry_run: bool = False, min_bytes: Optional[int] = None) -> bool:
    """Download a file using wget"""
    if dry_run:
        print(f'  [DRY RUN] Would download: {url}')
        return True

    print(f'  Downloading: {output_path.name} ...')
    try:
        result = subprocess.run(
            ['wget', '-q', '--show-progress', '-O', str(output_path), url],
            capture_output=True,
            text=True,
            timeout=600  # 10 minutes timeout
        )
        if result.returncode == 0:
            if min_bytes is not None:
                try:
                    size = output_path.stat().st_size
                except OSError as e:
                    print(f'  ✗ Cannot stat downloaded file: {e}')
                    return False

                if size < min_bytes:
                    print(
                        f'  ✗ Downloaded file too small: {size} bytes '
                        f'(expected >= {min_bytes} bytes). '
                        'Possible truncated download or error page.'
                    )
                    try:
                        output_path.unlink(missing_ok=True)
                    except OSError:
                        pass
                    return False

            ok, reason = _validate_downloaded_peak_file(output_path)
            if not ok:
                print(f'  ✗ Downloaded file validation failed: {reason}')
                try:
                    output_path.unlink(missing_ok=True)
                except OSError:
                    pass
                return False

            print(f'  ✓ Downloaded: {output_path.name}')
            return True
        else:
            print(f'  ✗ Failed: {result.stderr}')
            return False
    except Exception as e:
        print(f'  ✗ Error: {e}')
        return False


def generate_metadata(mark_type: str, cell_line: str, file_info: dict) -> dict:
    """Generate metadata JSON for an experiment"""
    cell_info = CELL_LINE_METADATA[cell_line]

    # Determine data source based on URL
    url = file_info['url']
    if 'UwHistone' in url or 'wgEncodeUw' in url:
        source_database = 'ENCODE_UW'
        antibody_source = 'University of Washington'
        encode_accession = f'UW_{cell_line}_{mark_type}'
        biosample_accession = f'UW_BS_{cell_line}'
    elif 'SydhHistone' in url or 'wgEncodeSydh' in url:
        source_database = 'ENCODE_Sydh'
        antibody_source = 'Snyder Lab (USC)'
        encode_accession = f'SYDH_{cell_line}_{mark_type}'
        biosample_accession = f'SYDH_BS_{cell_line}'
    else:
        source_database = 'ENCODE_Broad'
        antibody_source = 'Broad Institute'
        encode_accession = f'BROAD_{cell_line}_{mark_type}'
        biosample_accession = f'BROAD_BS_{cell_line}'

    peak_type = file_info.get("peak_type") or "broad"

    metadata = {
        'mark_type': mark_type,
        'encode_accession': encode_accession,
        'biosample_accession': biosample_accession,
        'tissue_type': cell_info['tissue_type'],
        'cell_type': cell_info['cell_type'],
        'cell_line': cell_line,
        'category': cell_info.get('category', 'unknown'),
        'treatment': file_info.get('treatment'),
        'developmental_stage': 'embryonic' if cell_line == 'H1-hESC' else 'adult',
        'antibody_target': mark_type,
        'antibody_source': antibody_source,
        'replicate_type': 'pooled',
        'source_database': source_database,
        'peak_type': peak_type,
        'genome_assembly': 'hg19',
        'data_source': 'UCSC_ENCODE',
        'download_url': url,
    }

    return metadata


def download_mark_data(mark_type: str, cell_lines: List[str], output_dir: Path, dry_run: bool = False):
    """Download data for a specific mark type across multiple cell lines"""
    print(f'\n{"="*60}')
    print(f'Mark: {mark_type}')
    print(f'{"="*60}')

    downloaded = []

    for cell_line in cell_lines:
        if cell_line not in ENCODE_FILES:
            print(f'  ⚠️  {cell_line} not available')
            continue

        if mark_type not in ENCODE_FILES[cell_line]:
            print(f'  ⚠️  {mark_type} not available for {cell_line}')
            continue

        file_info = ENCODE_FILES[cell_line][mark_type]

        print(f'\n  Cell line: {cell_line}')
        size_mb = file_info.get("size_mb")
        if size_mb is not None:
            print(f'  File size: ~{size_mb} MB')
        else:
            print('  File size: unknown')

        # Download peaks file
        peaks_filename = file_info['file']
        peaks_path = output_dir / peaks_filename

        # Even tiny HTML error pages are typically <<100KB; real peaks are much larger.
        min_bytes = int(file_info.get("min_bytes", 100 * 1024))

        if download_file(file_info['url'], peaks_path, dry_run=dry_run, min_bytes=min_bytes):
            # Generate metadata
            metadata = generate_metadata(mark_type, cell_line, file_info)
            metadata_path = output_dir / f'{mark_type}_{cell_line}_metadata.json'

            if dry_run:
                print(f'  [DRY RUN] Would write metadata: {metadata_path.name}')
            else:
                with open(metadata_path, 'w') as f:
                    json.dump(metadata, f, indent=2)

                print(f'  ✓ Metadata: {metadata_path.name}')

            downloaded.append({
                'mark_type': mark_type,
                'cell_line': cell_line,
                'peaks_file': str(peaks_path),
                'metadata_file': str(metadata_path),
            })

    return downloaded


def generate_batch_import_config(experiments: List[dict], output_dir: Path):
    """Generate batch import configuration file"""
    config = {
        'species': 'human',
        'experiments': experiments,
        'options': {
            'batch_size': 10000,
            'compute_associations': True,
            'parallel': 3,
        }
    }

    config_file = output_dir / 'encode_batch_import_config.json'
    with open(config_file, 'w') as f:
        json.dump(config, f, indent=2)

    print(f'\n{"="*60}')
    print('✓ Batch import config generated')
    print(f'{"="*60}')
    print(f'Config file: {config_file}')
    print(f'Total experiments: {len(experiments)}')

    return config_file


def parse_args():
    parser = argparse.ArgumentParser(
        description='Download ENCODE histone modification data from UCSC',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Download all Phase 2.4 marks for GM12878
  python3 download_encode_chipseq.py --all --cell-line GM12878

  # Download H3K27me3 for multiple cell lines
  python3 download_encode_chipseq.py --mark H3K27me3 --cell-line GM12878 K562 H1-hESC

  # Dry run to see what would be downloaded
  python3 download_encode_chipseq.py --all --cell-line GM12878 --dry-run
        """
    )

    parser.add_argument('--mark', choices=['H3K27me3', 'H3K4me1', 'H3K4me3', 'H3K27ac', 'H3K9me3', 'H3K36me3', 'H3K9ac', 'H3K4me2'],
                        help='Mark type to download')
    parser.add_argument('--cell-line', nargs='+', default=['GM12878'],
                        choices=list(ENCODE_FILES.keys()),
                        help='Cell lines to download (default: GM12878)')
    parser.add_argument('--all', action='store_true',
                        help='Download all available marks for selected cell lines')
    parser.add_argument('--output', default='encode_chipseq_data',
                        help='Output directory (default: encode_chipseq_data)')
    parser.add_argument('--dry-run', action='store_true',
                        help='Show what would be downloaded without actually downloading')

    return parser.parse_args()


def main():
    args = parse_args()

    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    print('='*60)
    print('ENCODE Histone Modification Data Downloader')
    print('='*60)
    print('Source: UCSC ENCODE DCC (hg19)')
    print(f'Output: {output_dir}')
    print(f'Cell lines: {", ".join(args.cell_line)}')
    if args.dry_run:
        print('Mode: DRY RUN (no actual downloads)')

    all_experiments = []

    if args.all:
        # Collect all available marks across selected cell lines
        available_marks = set()
        for cell_line in args.cell_line:
            if cell_line in ENCODE_FILES:
                available_marks.update(ENCODE_FILES[cell_line].keys())

        # Download all available marks
        for mark in sorted(available_marks):
            experiments = download_mark_data(mark, args.cell_line, output_dir, args.dry_run)
            all_experiments.extend(experiments)
    else:
        if not args.mark:
            print('Error: --mark is required when not using --all')
            return 1

        experiments = download_mark_data(args.mark, args.cell_line, output_dir, args.dry_run)
        all_experiments.extend(experiments)

    # Generate batch import config
    if all_experiments and not args.dry_run:
        config_file = generate_batch_import_config(all_experiments, output_dir)
        print('\n✨ Ready to import!')
        print(f'   Next: python3 scripts/batch_import_chipseq.py {config_file}')
    elif args.dry_run:
        print('\n📋 Dry run complete. Run without --dry-run to download.')
        print(f'   Total files to download: {len(all_experiments)}')
        total_size = 0.0
        unknown_sizes = 0
        for exp in all_experiments:
            size_mb = ENCODE_FILES[exp['cell_line']][exp['mark_type']].get('size_mb')
            if size_mb is None:
                unknown_sizes += 1
                continue
            try:
                total_size += float(size_mb)
            except (TypeError, ValueError):
                unknown_sizes += 1

        if unknown_sizes > 0:
            print(f'   Estimated total size: >= {total_size:.1f} MB (+{unknown_sizes} unknown)')
        else:
            print(f'   Estimated total size: ~{total_size:.1f} MB')


if __name__ == '__main__':
    main()
