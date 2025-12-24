"""
Phase 9.23 修复验证测试

覆盖修复点:
- P0-1: /genomes 白名单添加 .bb/.bigbed (BigBed 格式)
- P0-2: /statistics 端点 mark_type/cell_type 添加输入限制
- P0-2: /export 端点 mark_type/cell_type 添加输入限制

运行方式:
    pytest tests/test_phase_9_23_fixes.py -v
    pytest tests/test_phase_9_23_fixes.py -v -m unit         # 仅单元测试
"""
import pytest
from fastapi import HTTPException

from app.mounts.genomes import ALLOWED_GENOME_EXTENSIONS
from app.core.validators import parse_comma_list, MAX_COMMA_SEPARATED_ITEMS, MAX_FIELD_LENGTH


# ============== P0-1: genomes 白名单测试 ==============

class TestGenomesWhitelist:
    """测试 /genomes 文件扩展名白名单"""

    @pytest.mark.unit
    def test_bigbed_extensions_allowed(self):
        """验证 .bb 和 .bigbed 扩展名在白名单中"""
        assert '.bb' in ALLOWED_GENOME_EXTENSIONS, ".bb should be in whitelist"
        assert '.bigbed' in ALLOWED_GENOME_EXTENSIONS, ".bigbed should be in whitelist"

    @pytest.mark.unit
    def test_bigwig_extensions_still_allowed(self):
        """验证 .bw 和 .bigwig 扩展名仍在白名单中"""
        assert '.bw' in ALLOWED_GENOME_EXTENSIONS
        assert '.bigwig' in ALLOWED_GENOME_EXTENSIONS

    @pytest.mark.unit
    def test_common_genome_extensions_allowed(self):
        """验证常见基因组文件扩展名在白名单中"""
        common_extensions = ['.fa', '.fasta', '.fai', '.gz', '.bed', '.2bit']
        for ext in common_extensions:
            assert ext in ALLOWED_GENOME_EXTENSIONS, f"{ext} should be in whitelist"

    @pytest.mark.unit
    def test_dangerous_extensions_not_allowed(self):
        """验证危险文件扩展名不在白名单中"""
        dangerous_extensions = ['.py', '.sh', '.env', '.json', '.yaml', '.exe']
        for ext in dangerous_extensions:
            assert ext not in ALLOWED_GENOME_EXTENSIONS, f"{ext} should NOT be in whitelist"


# ============== P0-2: parse_comma_list 输入限制测试 ==============

class TestParseCommaListSecurity:
    """测试 parse_comma_list 输入限制 - 防止 DoS 攻击"""

    @pytest.mark.unit
    def test_valid_input(self):
        """正常输入应通过验证"""
        result = parse_comma_list("H3K27me3,H3K4me3", param_name="mark_type")
        assert result == ["H3K27me3", "H3K4me3"]

    @pytest.mark.unit
    def test_none_input_returns_none(self):
        """None 输入返回 None"""
        result = parse_comma_list(None, param_name="mark_type")
        assert result is None

    @pytest.mark.unit
    def test_empty_input_returns_none(self):
        """空字符串返回 None"""
        result = parse_comma_list("", param_name="mark_type")
        assert result is None

    @pytest.mark.unit
    def test_too_many_items_raises_400(self):
        """超过最大项数限制时抛出 400"""
        # 创建超过限制的项数 (默认 MAX_COMMA_SEPARATED_ITEMS = 20)
        too_many_items = ",".join([f"item{i}" for i in range(MAX_COMMA_SEPARATED_ITEMS + 5)])

        with pytest.raises(HTTPException) as exc_info:
            parse_comma_list(too_many_items, param_name="mark_type")

        assert exc_info.value.status_code == 400
        assert "Maximum" in exc_info.value.detail and "items allowed" in exc_info.value.detail

    @pytest.mark.unit
    def test_item_too_long_raises_400(self):
        """单项超过长度限制时抛出 400"""
        # 创建超长的单个项 (默认 MAX_ITEM_LENGTH = 50)
        long_item = "x" * 100

        with pytest.raises(HTTPException) as exc_info:
            parse_comma_list(long_item, param_name="mark_type")

        assert exc_info.value.status_code == 400
        assert "too long" in exc_info.value.detail

    @pytest.mark.unit
    def test_total_length_too_long_raises_400(self):
        """总长度超过限制时抛出 400"""
        # 创建超长的输入 (MAX_FIELD_LENGTH = 500)
        long_input = "x" * (MAX_FIELD_LENGTH + 100)

        with pytest.raises(HTTPException) as exc_info:
            parse_comma_list(long_input, param_name="mark_type")

        assert exc_info.value.status_code == 400
        assert "Input too long" in exc_info.value.detail

    @pytest.mark.unit
    def test_max_allowed_items_pass(self):
        """恰好达到最大项数限制应通过"""
        max_items = ",".join([f"item{i}" for i in range(MAX_COMMA_SEPARATED_ITEMS)])
        result = parse_comma_list(max_items, param_name="mark_type")
        assert len(result) == MAX_COMMA_SEPARATED_ITEMS

    @pytest.mark.unit
    def test_whitespace_trimmed(self):
        """验证空格被正确去除"""
        result = parse_comma_list("  H3K27me3  ,  H3K4me3  ", param_name="mark_type")
        assert result == ["H3K27me3", "H3K4me3"]

    @pytest.mark.unit
    def test_empty_items_filtered(self):
        """验证空项被过滤"""
        result = parse_comma_list("H3K27me3,,H3K4me3,", param_name="mark_type")
        assert result == ["H3K27me3", "H3K4me3"]


# ============== 常量验证测试 ==============

class TestSecurityConstants:
    """验证安全常量设置合理"""

    @pytest.mark.unit
    def test_max_items_reasonable(self):
        """MAX_COMMA_SEPARATED_ITEMS 应该是合理的值"""
        assert MAX_COMMA_SEPARATED_ITEMS >= 10, "Should allow at least 10 items"
        assert MAX_COMMA_SEPARATED_ITEMS <= 100, "Should not allow more than 100 items"

    @pytest.mark.unit
    def test_max_field_length_reasonable(self):
        """MAX_FIELD_LENGTH 应该是合理的值"""
        assert MAX_FIELD_LENGTH >= 100, "Should allow at least 100 characters"
        assert MAX_FIELD_LENGTH <= 10000, "Should not allow more than 10000 characters"
