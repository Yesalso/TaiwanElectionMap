import pandas as pd
from pathlib import Path


def summarize_and_save_copy(file_path, output_path=None, keywords=("里", "村")):
    """
    读取 Excel，按 市/区/(里|村) 分组求和。

    处理规则：
      1. 数据中间有空行 → 跳过继续（只丢整行全空的行）
      2. 空单元格 / 空列   → 视为 0，仍然求和 + 算百分比
      3. 同乡镇同名的里/村 → 合并为一行
      4. 结果保存为 原文件名_副本.xlsx（不覆盖原文件）
    """
    file_path = Path(file_path)
    if not file_path.exists():
        raise FileNotFoundError(f"文件不存在：{file_path}")

    if output_path is None:
        output_path = file_path.with_name(file_path.stem + "_副本" + file_path.suffix)
    else:
        output_path = Path(output_path)

    # 1) 读取所有 sheet 并合并
    xls = pd.ExcelFile(file_path)
    frames = []
    for sheet in xls.sheet_names:
        d = pd.read_excel(xls, sheet_name=sheet, header=None, dtype=str)
        if not d.empty:
            frames.append(d)
    if not frames:
        raise ValueError("Excel 中没有数据。")

    df = pd.concat(frames, ignore_index=True, sort=False)
    df.columns = range(df.shape[1])       # 防止重复列名

    # 2) 归一化空值：NaN / None / 空白 / "nan" / "None" 全部变成 ""
    df = df.astype(object).where(pd.notna(df), "")
    for col in df.columns:
        df[col] = (
            df[col].astype(str)
            .str.replace("\u3000", " ", regex=False)   # 全角空格 → 半角
            .str.strip()
        )
    df = df.replace({"nan": "", "None": "", "NaN": "", "NaT": ""}, regex=False)

    # 3) 删除整行全空的行（中间夹的空行会被跳过，后面数据继续保留）
    row_has_data = ~(df == "").all(axis=1)
    df = df[row_has_data].reset_index(drop=True)

    if df.empty:
        raise ValueError("Excel 中没有有效数据行。")
    if df.shape[1] < 3:
        raise ValueError("Excel 列数不足 3 列。")

    # 4) 过滤：只保留第三列含 "里" 或 "村" 的行（基层行政单位）
    pattern = "|".join(keywords)
    df = df[df[2].str.contains(pattern, na=False)].reset_index(drop=True)
    if df.empty:
        raise ValueError(f"未找到第三列包含 {'/'.join(keywords)} 的数据行。")

    # 5) 数值列：从第 4 列开始，空值/空列一律当 0
    value_cols = []
    for col_idx in range(3, df.shape[1]):
        s = df[col_idx].str.replace(r"[,\s，]", "", regex=True)   # 去千分位/空格/全角逗号
        s = s.replace({"": "0"})                                  # 空 → 0
        s = pd.to_numeric(s, errors="coerce").fillna(0)           # 无法解析 → 0
        df[col_idx] = s
        value_cols.append(col_idx)

    # 6) 按 市/区/里(村) 分组求和（同名合并）
    grouped = df.groupby([0, 1, 2], as_index=False)[value_cols].sum()

    # 7) 行最大值用于算百分比（全 0 行 → 百分比全 0）
    row_max = grouped[value_cols].max(axis=1).replace(0, pd.NA)

    # 8) 构造输出
    result = grouped[[0, 1, 2]].copy()
    result.columns = ["市", "區", "里"]
    for i, col in enumerate(value_cols, start=1):
        result[f"數值{i}"] = grouped[col].values
        pct = (grouped[col] / row_max * 100).fillna(0).round(2)
        result[f"百分比{i}"] = pct.values

    # 9) 保存到 _副本（不覆盖原文件）
    try:
        with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
            result.to_excel(writer, index=False, sheet_name="Sheet1")
    except PermissionError:
        raise PermissionError(f"写入失败：请先关闭正在占用的文件\n{output_path}")

    print("✅ 汇总完成")
    print(f"  sheet 数：{len(xls.sheet_names)}")
    print(f"  原始行数（含里/村）：{len(df)}")
    print(f"  合并后行数：{len(result)}")
    print(f"  数值列数（含空列）：{len(value_cols)}")
    print(f"  输出列名：{list(result.columns)}")
    print(f"  输出文件：{output_path}")
    return str(output_path)


if __name__ == "__main__":
    src = r"C:\Users\Windows\Desktop\工作簿1.xlsx"
    summarize_and_save_copy(src)