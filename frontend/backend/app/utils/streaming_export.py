"""
真流式导出工具

解决原有伪流式导出的内存问题：
- 原方案：先将所有数据加载到 DataFrame/BytesIO，再返回 StreamingResponse
- 新方案：使用生成器逐行 yield，永不在内存中保存完整数据集

支持格式:
- CSV: 逐行生成，内存占用 O(1)
- Excel: 使用 openpyxl write_only 模式，分块写入
- JSON Lines: 逐行 JSON 格式（便于大数据流处理）

Usage:
    from app.utils.streaming_export import stream_csv_response, stream_excel_response

    @router.get("/export")
    def export_data(db: Session = Depends(get_db)):
        def row_generator():
            result = db.execute(query)
            for row in result:
                yield dict(row._mapping)

        return stream_csv_response(
            row_generator(),
            fieldnames=["col1", "col2"],
            filename="export.csv"
        )
"""
import csv
import io
import json
import re
from typing import Any, Callable, Dict, Generator, Iterator, List, Optional

from fastapi.responses import StreamingResponse

from app.utils.http_headers import content_disposition_attachment


# CSV 公式注入防护正则：匹配以 =, +, -, @, \t, \r 开头的字符串
_CSV_FORMULA_PATTERN = re.compile(r'^[=+\-@\t\r]')


def sanitize_csv_value(value: Any) -> Any:
    """
    对 CSV 单元格值进行公式注入防护

    安全措施：
    - 以 =, +, -, @, \\t, \\r 开头的字符串前添加单引号
    - 防止 Excel/Sheets 将内容解释为公式执行

    Args:
        value: 原始值

    Returns:
        经过转义的安全值（非字符串类型原样返回）

    Example:
        >>> sanitize_csv_value("=CMD|'/C calc'!A0")
        "'=CMD|'/C calc'!A0"
        >>> sanitize_csv_value(123)
        123
    """
    if not isinstance(value, str):
        return value

    if _CSV_FORMULA_PATTERN.match(value):
        return "'" + value

    return value


def sanitize_row(row: Dict[str, Any]) -> Dict[str, Any]:
    """
    对整行数据进行 CSV 公式注入防护

    Args:
        row: 原始行数据字典

    Returns:
        经过转义的安全行数据
    """
    return {k: sanitize_csv_value(v) for k, v in row.items()}


def stream_csv_rows(
    rows: Iterator[Dict[str, Any]],
    fieldnames: List[str],
    *,
    delimiter: str = ",",
    include_header: bool = True,
    sanitize: bool = True,
) -> Generator[bytes, None, None]:
    """
    逐行生成 CSV 数据的字节流

    Args:
        rows: 字典迭代器（每个字典为一行数据）
        fieldnames: 列名列表，决定输出顺序
        delimiter: 分隔符（默认逗号，可设为 \\t 输出 TSV）
        include_header: 是否包含表头行
        sanitize: 是否对数据进行公式注入防护（默认 True）

    Yields:
        每行 CSV 数据的 UTF-8 字节

    Security:
        默认启用公式注入防护，防止恶意数据在 Excel 中执行。
        以 =, +, -, @, \\t, \\r 开头的字符串会被添加前缀单引号。
    """
    # 使用 StringIO 作为缓冲区（每行独立）
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=fieldnames, delimiter=delimiter,
                            extrasaction='ignore')

    # 输出表头
    if include_header:
        writer.writeheader()
        yield buffer.getvalue().encode("utf-8")
        buffer.seek(0)
        buffer.truncate()

    # 逐行输出数据（带公式注入防护）
    for row in rows:
        safe_row = sanitize_row(row) if sanitize else row
        writer.writerow(safe_row)
        yield buffer.getvalue().encode("utf-8")
        buffer.seek(0)
        buffer.truncate()


def stream_csv_response(
    rows: Iterator[Dict[str, Any]],
    fieldnames: List[str],
    filename: str,
    *,
    delimiter: str = ",",
) -> StreamingResponse:
    """
    创建 CSV 流式响应

    Args:
        rows: 字典迭代器
        fieldnames: 列名列表
        filename: 下载文件名
        delimiter: 分隔符

    Returns:
        FastAPI StreamingResponse
    """
    media_type = "text/csv" if delimiter == "," else "text/tab-separated-values"

    return StreamingResponse(
        stream_csv_rows(rows, fieldnames, delimiter=delimiter),
        media_type=media_type,
        # SECURITY: 防止 CRLF 注入/响应拆分，统一使用安全的 Content-Disposition 构造
        headers={"Content-Disposition": content_disposition_attachment(filename)},
    )


def stream_jsonl_rows(
    rows: Iterator[Dict[str, Any]],
    *,
    encoder: Optional[Callable[[Any], str]] = None,
) -> Generator[bytes, None, None]:
    """
    逐行生成 JSON Lines 格式数据

    JSON Lines (JSONL) 格式：每行一个独立的 JSON 对象
    优点：易于流式处理、支持增量解析、内存效率高

    Args:
        rows: 字典迭代器
        encoder: 自定义 JSON 编码函数（用于处理特殊类型）

    Yields:
        每行 JSON 数据的 UTF-8 字节
    """
    json_dumps = encoder or json.dumps

    for row in rows:
        yield (json_dumps(row, ensure_ascii=False, default=str) + "\n").encode("utf-8")


def stream_jsonl_response(
    rows: Iterator[Dict[str, Any]],
    filename: str,
) -> StreamingResponse:
    """
    创建 JSON Lines 流式响应

    Args:
        rows: 字典迭代器
        filename: 下载文件名

    Returns:
        FastAPI StreamingResponse
    """
    return StreamingResponse(
        stream_jsonl_rows(rows),
        media_type="application/x-ndjson",
        # SECURITY: 防止 CRLF 注入/响应拆分，统一使用安全的 Content-Disposition 构造
        headers={"Content-Disposition": content_disposition_attachment(filename)},
    )


def stream_excel_response(
    rows: Iterator[Dict[str, Any]],
    fieldnames: List[str],
    filename: str,
    *,
    sheet_name: str = "Data",
    chunk_size: int = 1000,
    sanitize: bool = True,
) -> StreamingResponse:
    """
    创建 Excel 流式响应

    注意：Excel 格式本质上是 ZIP 压缩包，无法实现真正的字节流式传输。
    此实现使用 openpyxl write_only 模式减少内存峰值：
    - write_only 模式：行写入后立即释放内存
    - 最终仍需在内存中生成完整文件

    对于超大数据集（>100k 行），建议使用 CSV 格式。

    Args:
        rows: 字典迭代器
        fieldnames: 列名列表
        filename: 下载文件名
        sheet_name: Excel 工作表名称
        chunk_size: 处理块大小（用于日志）
        sanitize: 是否对数据进行公式注入防护（默认 True）

    Returns:
        FastAPI StreamingResponse

    Security:
        默认启用公式注入防护，防止恶意数据在 Excel 中执行。
    """
    # 延迟导入 openpyxl（非必需依赖）
    try:
        from openpyxl import Workbook
    except ImportError:
        raise ImportError("openpyxl is required for Excel export. Install with: pip install openpyxl")

    # 使用 write_only 模式减少内存占用
    wb = Workbook(write_only=True)
    ws = wb.create_sheet(title=sheet_name)

    # 写入表头
    ws.append(fieldnames)

    # 逐行写入数据（带公式注入防护）
    for row in rows:
        safe_row = sanitize_row(row) if sanitize else row
        ws.append([safe_row.get(field) for field in fieldnames])

    # 保存到内存缓冲区
    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)

    return StreamingResponse(
        buffer,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        # SECURITY: 防止 CRLF 注入/响应拆分，统一使用安全的 Content-Disposition 构造
        headers={"Content-Disposition": content_disposition_attachment(filename)},
    )


def create_db_row_generator(
    db_execute_result,
    *,
    transform: Optional[Callable[[Dict[str, Any]], Dict[str, Any]]] = None,
) -> Generator[Dict[str, Any], None, None]:
    """
    从数据库查询结果创建行生成器

    Args:
        db_execute_result: SQLAlchemy execute() 返回的结果
        transform: 可选的行转换函数

    Yields:
        每行数据的字典
    """
    for row in db_execute_result:
        row_dict = dict(row._mapping)
        if transform:
            row_dict = transform(row_dict)
        yield row_dict


__all__ = [
    "stream_csv_rows",
    "stream_csv_response",
    "stream_jsonl_rows",
    "stream_jsonl_response",
    "stream_excel_response",
    "create_db_row_generator",
]
