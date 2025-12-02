/**
 * 物种名称翻译工具
 * 统一处理中英文物种名映射
 */

// 物种名到 i18n key 的映射
export const SPECIES_NAME_TO_KEY: Record<string, string> = {
  // 中文名
  '人类': 'human',
  '黑猩猩': 'chimpanzee',
  '猕猴': 'macaque',
  '狨猴': 'marmoset',
  // 英文名
  'Human': 'human',
  'Chimpanzee': 'chimpanzee',
  'Macaque': 'macaque',
  'Marmoset': 'marmoset',
  // 小写
  'human': 'human',
  'chimpanzee': 'chimpanzee',
  'macaque': 'macaque',
  'marmoset': 'marmoset',
}

/**
 * 获取物种名对应的 i18n key
 * @param speciesName 物种名称（中文或英文）
 * @returns i18n key，如 'human', 'chimpanzee' 等
 */
export function getSpeciesKey(speciesName: string): string | undefined {
  return SPECIES_NAME_TO_KEY[speciesName]
}

/**
 * 创建物种名翻译函数
 * @param t 翻译函数，通常是 useTranslation('common') 返回的 t
 * @returns 翻译后的物种名
 */
export function createSpeciesTranslator(t: (key: string) => string) {
  return (speciesName: string): string => {
    const key = SPECIES_NAME_TO_KEY[speciesName]
    return key ? t(`species.${key}`) : speciesName
  }
}
