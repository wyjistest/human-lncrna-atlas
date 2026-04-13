export async function copyText(text: string): Promise<boolean> {
  const writeText = globalThis.navigator?.clipboard?.writeText?.bind(globalThis.navigator.clipboard)
  if (!writeText) return false

  try {
    await writeText(text)
    return true
  } catch (error) {
    console.error('Copy text failed:', error)
    return false
  }
}
