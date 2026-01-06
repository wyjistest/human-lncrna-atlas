/**
 * PDF 报告导出工具
 * 使用 jsPDF + html2canvas 动态导入，减少首屏 bundle
 *
 * v2.0: 修复分页问题 - 使用 Canvas 分片裁剪，避免内容溢出
 */

export interface PDFExportOptions {
  title?: string
  includeTimestamp?: boolean
  filename?: string
}

/**
 * 导出 HTML 元素为 PDF（支持正确分页）
 * @param element 要导出的 DOM 元素
 * @param options 导出选项
 */
export async function exportToPDF(
  element: HTMLElement,
  options: PDFExportOptions = {}
): Promise<boolean> {
  const {
    title = 'Human LncRNA Atlas Report',
    includeTimestamp = true,
    filename = 'lncrna-atlas-report'
  } = options

  try {
    // 动态导入，减少首屏 bundle
    const [{ jsPDF }, { default: html2canvas }] = await Promise.all([
      import('jspdf'),
      import('html2canvas')
    ])

    // 截图配置
    const canvas = await html2canvas(element, {
      scale: 2,
      useCORS: true,
      backgroundColor: '#ffffff',
      logging: false,
      allowTaint: true
    })

    // 创建 PDF（A4 尺寸）
    const pdf = new jsPDF({
      orientation: 'portrait',
      unit: 'mm',
      format: 'a4'
    })

    const pageWidth = pdf.internal.pageSize.getWidth()
    const pageHeight = pdf.internal.pageSize.getHeight()
    const margin = 15

    // 计算尺寸
    const contentWidth = pageWidth - margin * 2
    const headerHeight = includeTimestamp ? 35 : 25
    const footerHeight = 15

    // 首页和后续页的可用内容高度不同
    const firstPageContentHeight = pageHeight - headerHeight - footerHeight
    const normalPageContentHeight = pageHeight - margin - footerHeight

    // 图片缩放比例（PDF 宽度 / 源 canvas 宽度）
    const imgScale = contentWidth / canvas.width

    // 缩放后的图片总高度（mm）
    const scaledImgHeight = canvas.height * imgScale

    // 计算需要多少页
    let remainingHeight = scaledImgHeight
    let pageCount = 0

    // 首页
    if (remainingHeight > 0) {
      pageCount++
      remainingHeight -= firstPageContentHeight
    }
    // 后续页
    while (remainingHeight > 0) {
      pageCount++
      remainingHeight -= normalPageContentHeight
    }

    const totalPages = Math.max(1, pageCount)

    // 逐页渲染
    let srcYOffset = 0 // 源图片 Y 偏移（像素）

    for (let page = 0; page < totalPages; page++) {
      if (page > 0) pdf.addPage()

      // 当前页可用高度（mm）
      const availableHeight = page === 0 ? firstPageContentHeight : normalPageContentHeight

      // 计算当前页需要的源图片高度（像素）
      const srcSliceHeight = Math.min(
        availableHeight / imgScale,
        canvas.height - srcYOffset
      )

      if (srcSliceHeight <= 0) break

      // 添加标题（仅首页）
      if (page === 0) {
        pdf.setFontSize(18)
        pdf.setFont('helvetica', 'bold')
        pdf.text(title, pageWidth / 2, 20, { align: 'center' })

        if (includeTimestamp) {
          pdf.setFontSize(10)
          pdf.setFont('helvetica', 'normal')
          pdf.setTextColor(128)
          pdf.text(
            `Generated: ${new Date().toLocaleString('en-US')}`,
            pageWidth / 2,
            28,
            { align: 'center' }
          )
          pdf.setTextColor(0)
        }
      }

      // 创建裁剪后的 canvas 片段
      const sliceCanvas = document.createElement('canvas')
      sliceCanvas.width = canvas.width
      sliceCanvas.height = Math.ceil(srcSliceHeight)

      const ctx = sliceCanvas.getContext('2d')
      if (!ctx) throw new Error('Failed to get canvas context')

      // 从源 canvas 裁剪指定区域
      ctx.drawImage(
        canvas,
        0, srcYOffset,                    // 源起点 (sx, sy)
        canvas.width, srcSliceHeight,     // 源尺寸 (sWidth, sHeight)
        0, 0,                             // 目标起点 (dx, dy)
        canvas.width, srcSliceHeight      // 目标尺寸 (dWidth, dHeight)
      )

      // 转换为图片数据
      const sliceImgData = sliceCanvas.toDataURL('image/png')

      // 计算目标位置和尺寸
      const destY = page === 0 ? headerHeight : margin
      const destHeight = srcSliceHeight * imgScale

      // 添加裁剪后的图片到 PDF
      pdf.addImage(
        sliceImgData,
        'PNG',
        margin,
        destY,
        contentWidth,
        destHeight,
        undefined,
        'FAST'
      )

      // 更新源偏移
      srcYOffset += srcSliceHeight
    }

    // 添加页脚
    for (let i = 1; i <= totalPages; i++) {
      pdf.setPage(i)
      pdf.setFontSize(8)
      pdf.setTextColor(128)
      pdf.text(
        `Human LncRNA Atlas | Page ${i} / ${totalPages}`,
        pageWidth / 2,
        pageHeight - 10,
        { align: 'center' }
      )
    }

    // 下载
    pdf.save(`${filename}-${Date.now()}.pdf`)

    return true
  } catch (error) {
    console.error('PDF export failed:', error)
    return false
  }
}

/**
 * 导出多个 ECharts 图表为 PDF
 * @param charts 图表实例数组（带名称）
 * @param options 导出选项
 */
export async function exportChartsToPDF(
  charts: Array<{ instance: { getDataURL: (opts: object) => string }; name: string }>,
  options: PDFExportOptions = {}
): Promise<boolean> {
  const {
    // Note: title is available for future use (e.g., cover page)
    includeTimestamp = true,
    filename = 'lncrna-atlas-charts'
  } = options

  try {
    const { jsPDF } = await import('jspdf')

    const pdf = new jsPDF({
      orientation: 'landscape',
      unit: 'mm',
      format: 'a4'
    })

    const pageWidth = pdf.internal.pageSize.getWidth()
    const pageHeight = pdf.internal.pageSize.getHeight()
    const margin = 15

    charts.forEach((chart, index) => {
      if (index > 0) pdf.addPage()

      // 标题
      pdf.setFontSize(14)
      pdf.setFont('helvetica', 'bold')
      pdf.text(chart.name, pageWidth / 2, 15, { align: 'center' })

      // 获取图表图片
      const imgData = chart.instance.getDataURL({
        type: 'png',
        pixelRatio: 2,
        backgroundColor: '#fff'
      })

      // 添加图表
      const imgWidth = pageWidth - margin * 2
      const imgHeight = pageHeight - 40
      pdf.addImage(imgData, 'PNG', margin, 25, imgWidth, imgHeight)
    })

    // 添加封面信息
    pdf.setPage(1)
    if (includeTimestamp) {
      pdf.setFontSize(8)
      pdf.setTextColor(128)
      pdf.text(
        `Generated: ${new Date().toLocaleString('en-US')}`,
        pageWidth - margin,
        pageHeight - 10,
        { align: 'right' }
      )
    }

    pdf.save(`${filename}-${Date.now()}.pdf`)
    return true
  } catch (error) {
    console.error('Charts PDF export failed:', error)
    return false
  }
}
