import { describe, expect, it } from "vitest";
import { countChapterChars, countNonWhitespaceChars } from "./chapter-count";

describe("章节字数统计", () => {
  it("计入标点，不计空白和明确的章节标题", () => {
    expect(countChapterChars("第2章 完美的缺陷\n\n你好，世界！")).toBe(6);
  });

  it("首行是正文时不得误删", () => {
    expect(countChapterChars("他推开门。\n\n风停了。")).toBe(9);
  });

  it("选中文本同样计入标点并排除空白", () => {
    expect(countNonWhitespaceChars("你好， \n世界！")).toBe(6);
  });
});
