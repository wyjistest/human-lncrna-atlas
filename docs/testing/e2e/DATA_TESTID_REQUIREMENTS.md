# Phase 2.5 ChIP-seq Compare E2E Test - Required data-testid Attributes

> 更新（2026-01-24）：本文档为 E2E 可测试性改造建议清单（data-testid 规范），不代表当前开发待办；现状以 `docs/CURRENT_STATUS.md` 为准。
> 可追踪任务：https://github.com/wyjistest/human-lncrna-atlas/issues/75

This document lists the recommended `data-testid` attributes that should be added to frontend components to improve test reliability and maintainability.

## Overview

Using `data-testid` attributes provides several benefits:
- Tests are more resilient to UI changes (class names, text content)
- Clear documentation of testable components
- Better separation between styling and testing concerns
- Easier debugging when tests fail

## Required data-testid Attributes by Component

### ChIPSeqPeaksTable/index.tsx

```tsx
// Main container
<div data-testid="chipseq-container">

// Mark selector dropdown
<Select data-testid="mark-selector" />

// Compare marks button
<Button data-testid="compare-marks-button">Compare Marks</Button>

// Exit compare button (in compare mode)
<Button data-testid="exit-compare-button">Exit</Button>
```

### ChIPSeqPeaksTable/FilterPanel.tsx

```tsx
// Filter panel container
<div data-testid="filter-panel">

// Fold enrichment filter
<InputNumber data-testid="fold-enrichment-filter" />

// Q-value filter
<InputNumber data-testid="qvalue-filter" />

// Cell type filter
<Select data-testid="cell-type-filter" />

// Position filter
<Select data-testid="position-filter" />

// Reset filters button
<Button data-testid="reset-filters-button">Reset</Button>
```

### ChIPSeqPeaksTable/PeaksTable.tsx

```tsx
// Peaks data table
<Table data-testid="peaks-table" />

// Export BED button
<Button data-testid="export-bed-button">Export BED</Button>
```

### ChIPSeqPeaksTable/StatsCards.tsx

```tsx
// Statistics cards container
<div data-testid="stats-cards-container">

// Individual stat cards
<Card data-testid="stats-card-total-peaks">
<Card data-testid="stats-card-avg-signal">
<Card data-testid="stats-card-avg-fold">
```

### ChIPSeqPeaksTable/CompareCharts.tsx

```tsx
// Compare charts container
<div data-testid="compare-charts-container">

// Radar comparison chart
<div data-testid="radar-compare-chart">

// Bar comparison chart
<div data-testid="bar-compare-chart">

// Position distribution chart
<div data-testid="position-distribution-chart">
```

### ChIPSeqPeaksTable/CellLineHeatmapMatrix.tsx

```tsx
// Heatmap matrix container
<div data-testid="heatmap-matrix-container">

// Heatmap chart
<div data-testid="cell-line-matrix-chart">

// Metric selector
<Select data-testid="metric-selector" />
```

### ChIPSeqPeaksTable/BivalentDomainBadge.tsx

```tsx
// Bivalent domain badge
<Badge data-testid="bivalent-domain-badge">
```

### ChIPSeqPeaksTable/CellLineCompareView.tsx

```tsx
// Cell line compare container
<div data-testid="cell-line-compare-container">

// Cell line selector
<Checkbox.Group data-testid="cell-line-selector" />
```

### Navigation/Menu Components

```tsx
// Language switcher
<Dropdown data-testid="language-switcher">

// Main navigation menu
<Menu data-testid="main-navigation">

// User menu (if applicable)
<Dropdown data-testid="user-menu">
```

### Common Components

```tsx
// Loading spinner overlay
<Spin data-testid="loading-spinner" />

// Error alert
<Alert data-testid="error-alert" type="error" />

// Empty state
<Empty data-testid="empty-state" />

// Export button (generic)
<Button data-testid="export-button">

// Pagination
<Pagination data-testid="table-pagination" />
```

## Implementation Example

Here's how to add `data-testid` to an existing component:

### Before:
```tsx
<Card className="stats-card">
  <Statistic title="Total Peaks" value={totalPeaks} />
</Card>
```

### After:
```tsx
<Card className="stats-card" data-testid="stats-card-total-peaks">
  <Statistic title="Total Peaks" value={totalPeaks} />
</Card>
```

## View Mode Tabs (Compare Mode)

```tsx
// Merged view tab
<Tabs.TabPane data-testid="merged-view-tab" tab="Merged View">

// Parallel view tab
<Tabs.TabPane data-testid="parallel-view-tab" tab="Parallel View">

// Statistics view tab
<Tabs.TabPane data-testid="statistics-view-tab" tab="Statistics">

// Matrix view tab
<Tabs.TabPane data-testid="matrix-view-tab" tab="Matrix View">
```

## Best Practices

1. **Naming Convention**: Use kebab-case for all `data-testid` values
2. **Descriptive Names**: Names should describe the component's purpose
3. **Unique IDs**: Ensure each `data-testid` is unique within the component tree
4. **Container + Content**: Add testids to both containers and interactive elements
5. **Avoid Dynamic IDs**: Don't include dynamic data in testids (use for filtering in tests instead)

## Priority List

### High Priority (Required for basic test coverage):
- [x] `chipseq-container`
- [x] `mark-selector`
- [x] `compare-marks-button`
- [x] `exit-compare-button`
- [x] `peaks-table`
- [x] `filter-panel`
- [x] `export-button`

### Medium Priority (For comprehensive coverage):
- [x] `stats-cards-container`
- [x] `radar-compare-chart`
- [x] `cell-line-matrix-chart`
- [x] `bivalent-domain-badge`
- [x] `metric-selector`
- [x] `cell-type-filter`

### Low Priority (Nice to have):
- [ ] Individual stat cards
- [ ] View mode tabs
- [ ] Loading states
- [ ] Error states

## Notes

- These `data-testid` attributes are only used for testing and should not affect production functionality
- Consider using a utility function to strip `data-testid` in production builds if bundle size is a concern
- Some test frameworks (like Playwright) can use other locator strategies (role, text, label) which don't require `data-testid`
