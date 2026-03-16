import { expect, type Page } from '@playwright/test'

export async function switchLanguage(page: Page, optionPattern: RegExp) {
  const languageSwitcher = page.getByTestId('language-switcher')
  await expect(languageSwitcher).toBeVisible()
  await languageSwitcher.click()

  const languageOption = page.getByRole('option', { name: optionPattern }).first()
  await expect(languageOption).toBeVisible({ timeout: 5000 })
  await languageOption.click()
  await page.waitForTimeout(500)
}
