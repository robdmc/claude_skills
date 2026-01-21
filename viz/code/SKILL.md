---
name: viz
description: Visualization factory that generates matplotlib/seaborn plotting functions. Use when you need a function to create a specific visualization. Provide a natural language spec describing the plot type, data context, axis labels, title, and any special requirements. Returns executable Python function code.
allowed-tools: Read, Bash
---

# Viz Skill: Visualization Factory

## Purpose

This skill is a **visualization factory** - it receives natural language specifications from calling agents and returns publication-quality matplotlib/seaborn function code. The skill intelligently chooses the best library based on the request.

**Key pattern:**
1. Calling agent provides visualization spec with full context
2. Viz skill returns complete, executable Python function code
3. Calling agent executes in background sub-agent with `run_in_background: true`
4. User gets interactive plots that don't block the conversation

## Planning Agent

When requests are ambiguous, ask clarifying questions **to the calling agent** before generating code.

### When to Plan

Trigger planning when:
- Request is ambiguous (multiple valid visualization types)
- Missing critical context (axis labels, data semantics)
- Complex visualization with several valid approaches

### Planning Workflow

1. Analyze the request for ambiguity
2. Ask the calling agent specific clarifying questions
3. Receive answers and generate optimal function code

**Example planning interaction:**

*Request:* "Plot the distribution of housing prices"

*Respond with questions:*
> I have options for visualizing this distribution. To generate the best plot:
> 1. Should I show a histogram, KDE (smooth curve), or both overlaid?
> 2. Do you want to highlight statistical measures (mean, median, percentiles)?
> 3. Single distribution or compare across categories?

*After answers, generate the function.*

### When NOT to Plan

Skip planning when:
- Request is clear and specific (e.g., "scatter plot of x vs y with axis labels provided")
- Standard visualization with sufficient context
- Can make a good autonomous decision

## Refinement Workflow

When refining existing plots:

1. Calling agent sends original function code + requested changes
2. Generate updated function with refinements
3. Calling agent executes in background → **new plot window opens**
4. User has both plots visible for comparison

**Key behavior:** Refinements always create new plot windows. Old plots remain open unless user closes them.

**Example refinement request:**
> Refine this scatter plot function:
> [original function code]
> Changes: Increase point size, add colormap blue-to-red based on 'price' column

Generate updated function with `s=100` and `c=df['price'], cmap='coolwarm'`.

## Library Selection

### Use Seaborn When:
- **Statistical distributions**: histograms with KDE, violin plots, box plots, swarm plots
- **Relationship plots**: regression with confidence intervals (`regplot`, `lmplot`)
- **Categorical data**: bar plots with error bars, count plots, point plots
- **Pair-wise relationships**: pair plots, joint plots
- **Heatmaps**: correlation matrices, clustered heatmaps
- **DataFrame-centric workflows**: pandas DataFrames with semantic column names
- **Built-in statistical aggregation**: automatic mean/median with error bars

### Use Matplotlib When:
- **Fine-grained control**: custom tick labels, annotations, insets
- **Specialized plots**: quiver plots, contour plots, 3D plots
- **Custom layouts**: multiple axes with specific positioning
- **Non-statistical visualizations**: simple line plots, basic scatter without regression
- **Time series with date handling**: `plot_date()`, custom date formatting
- **When seaborn is overkill**: simple plots without statistical features

### Combine Both When:
Use seaborn for the base statistical plot, matplotlib for customizations:

```python
import seaborn as sns
import matplotlib.pyplot as plt

fig, ax = plt.subplots(figsize=(10, 6))
sns.regplot(x=x, y=y, ax=ax, scatter_kws={'alpha': 0.6})
ax.axhline(y=threshold, color='red', linestyle='--')  # matplotlib addition
ax.set_title('Regression with Threshold Line')
```

## Input Specification

Calling agents should provide:
- **Visualization type**: What kind of plot (scatter, line, histogram, etc.)
- **Data description**: What the data represents semantically
- **Axis labels**: What should appear on x/y axes (with units)
- **Title context**: What the plot should be titled
- **Special requirements**: Reference lines, annotations, color coding

**Example request:**
> Generate a function for a residual plot. Data is from linear regression predicting housing prices from square footage. X-axis: 'Predicted Price ($)', Y-axis: 'Residual ($)'. Include horizontal reference line at y=0. Title should indicate checking for heteroscedasticity.

## Output Format

Return a complete, executable Python function as a code block:

```python
def plot_residuals(y_true, y_pred):
    """
    Residual plot for housing price regression.
    Checks for heteroscedasticity in predictions.
    """
    import matplotlib.pyplot as plt
    import numpy as np

    residuals = np.array(y_true) - np.array(y_pred)

    fig, ax = plt.subplots(figsize=(10, 6))
    ax.scatter(y_pred, residuals, alpha=0.6, edgecolors='black', linewidth=0.5)
    ax.axhline(y=0, color='red', linestyle='--', linewidth=1.5, label='Zero residual')

    ax.set_xlabel('Predicted Price ($)', fontsize=12)
    ax.set_ylabel('Residual ($)', fontsize=12)
    ax.set_title('Residual Plot: Housing Price Regression\nChecking for Heteroscedasticity', fontsize=14)
    ax.legend()
    ax.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.show()
```

The calling agent then:
1. Writes a script that defines the function and calls it with data
2. Executes via `python3 /tmp/plot_script.py` with `run_in_background: true`

## Publication Quality Standards

### Labels & Titles
- Descriptive axis labels with units when applicable
- Clear, informative titles explaining what's shown
- Font sizes: 12pt+ for labels, 14pt+ for titles

### Visual Quality
- `figsize=(10, 6)` or appropriate aspect ratio
- `tight_layout()` to prevent clipping
- Grid lines with `alpha=0.3` for subtle guidance
- Scatter points with edge colors for visibility
- Alpha transparency when points may overlap

### Colors
- Use colorblind-friendly palettes (seaborn defaults, or matplotlib's 'viridis', 'coolwarm')
- Consistent color schemes within a plot
- Reference lines in distinct colors (red for zero lines, etc.)

### Code Style
- Imports inside the function for self-contained execution
- Docstring explaining what the plot shows
- Clear parameter names matching data semantics

## Visualization Catalog

### Distribution Plots

**Histogram with KDE** (seaborn)
```python
def plot_distribution(data, column, title, xlabel):
    import seaborn as sns
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(10, 6))
    sns.histplot(data=data, x=column, kde=True, ax=ax, edgecolor='black', alpha=0.7)

    ax.set_xlabel(xlabel, fontsize=12)
    ax.set_ylabel('Count', fontsize=12)
    ax.set_title(title, fontsize=14)
    plt.tight_layout()
    plt.show()
```

**Box Plot** (seaborn)
```python
def plot_boxplot(data, x_col, y_col, title, xlabel, ylabel):
    import seaborn as sns
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(10, 6))
    sns.boxplot(data=data, x=x_col, y=y_col, ax=ax, palette='Set2')

    ax.set_xlabel(xlabel, fontsize=12)
    ax.set_ylabel(ylabel, fontsize=12)
    ax.set_title(title, fontsize=14)
    plt.tight_layout()
    plt.show()
```

**Violin Plot** (seaborn)
```python
def plot_violin(data, x_col, y_col, title, xlabel, ylabel):
    import seaborn as sns
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(10, 6))
    sns.violinplot(data=data, x=x_col, y=y_col, ax=ax, palette='muted')

    ax.set_xlabel(xlabel, fontsize=12)
    ax.set_ylabel(ylabel, fontsize=12)
    ax.set_title(title, fontsize=14)
    plt.tight_layout()
    plt.show()
```

### Relationship Plots

**Scatter Plot** (matplotlib)
```python
def plot_scatter(x, y, title, xlabel, ylabel):
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(10, 6))
    ax.scatter(x, y, alpha=0.6, edgecolors='black', linewidth=0.5)

    ax.set_xlabel(xlabel, fontsize=12)
    ax.set_ylabel(ylabel, fontsize=12)
    ax.set_title(title, fontsize=14)
    ax.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.show()
```

**Regression Plot with CI** (seaborn)
```python
def plot_regression(data, x_col, y_col, title, xlabel, ylabel):
    import seaborn as sns
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(10, 6))
    sns.regplot(data=data, x=x_col, y=y_col, ax=ax,
                scatter_kws={'alpha': 0.5, 'edgecolors': 'black', 'linewidth': 0.5},
                line_kws={'color': 'red'})

    ax.set_xlabel(xlabel, fontsize=12)
    ax.set_ylabel(ylabel, fontsize=12)
    ax.set_title(title, fontsize=14)
    ax.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.show()
```

**Residual Plot** (seaborn or matplotlib)
```python
def plot_residuals(y_true, y_pred, title, xlabel='Fitted Values', ylabel='Residuals'):
    import matplotlib.pyplot as plt
    import numpy as np

    residuals = np.array(y_true) - np.array(y_pred)

    fig, ax = plt.subplots(figsize=(10, 6))
    ax.scatter(y_pred, residuals, alpha=0.6, edgecolors='black', linewidth=0.5)
    ax.axhline(y=0, color='red', linestyle='--', linewidth=1.5, label='Zero residual')

    ax.set_xlabel(xlabel, fontsize=12)
    ax.set_ylabel(ylabel, fontsize=12)
    ax.set_title(title, fontsize=14)
    ax.legend()
    ax.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.show()
```

### Comparison Plots

**Bar Plot with Error Bars** (seaborn)
```python
def plot_bar(data, x_col, y_col, title, xlabel, ylabel):
    import seaborn as sns
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(10, 6))
    sns.barplot(data=data, x=x_col, y=y_col, ax=ax, palette='Set2', errorbar='sd')

    ax.set_xlabel(xlabel, fontsize=12)
    ax.set_ylabel(ylabel, fontsize=12)
    ax.set_title(title, fontsize=14)
    plt.tight_layout()
    plt.show()
```

**Heatmap** (seaborn)
```python
def plot_heatmap(data, title, annot=True):
    import seaborn as sns
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(10, 8))
    sns.heatmap(data, annot=annot, cmap='coolwarm', center=0, ax=ax,
                fmt='.2f', linewidths=0.5)

    ax.set_title(title, fontsize=14)
    plt.tight_layout()
    plt.show()
```

### Time Series

**Line Plot with Dates** (matplotlib)
```python
def plot_timeseries(dates, values, title, xlabel, ylabel):
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates

    fig, ax = plt.subplots(figsize=(12, 6))
    ax.plot(dates, values, linewidth=1.5, marker='o', markersize=3)

    ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
    ax.xaxis.set_major_locator(mdates.AutoDateLocator())
    fig.autofmt_xdate()

    ax.set_xlabel(xlabel, fontsize=12)
    ax.set_ylabel(ylabel, fontsize=12)
    ax.set_title(title, fontsize=14)
    ax.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.show()
```

### Statistical Plots

**Pair Plot** (seaborn)
```python
def plot_pairplot(data, hue_col=None, title='Pair Plot'):
    import seaborn as sns
    import matplotlib.pyplot as plt

    g = sns.pairplot(data, hue=hue_col, diag_kind='kde', palette='Set2')
    g.fig.suptitle(title, y=1.02, fontsize=14)
    plt.tight_layout()
    plt.show()
```

**Joint Plot** (seaborn)
```python
def plot_joint(data, x_col, y_col, title):
    import seaborn as sns
    import matplotlib.pyplot as plt

    g = sns.jointplot(data=data, x=x_col, y=y_col, kind='reg', height=8)
    g.fig.suptitle(title, y=1.02, fontsize=14)
    plt.tight_layout()
    plt.show()
```

## Library Reference Table

| Category | Plot Types | Preferred Library | Functions |
|----------|-----------|-------------------|-----------|
| Distribution | histogram, KDE | seaborn | `histplot`, `kdeplot` |
| Distribution | box, violin | seaborn | `boxplot`, `violinplot` |
| Relationship | scatter (simple) | matplotlib | `scatter` |
| Relationship | regression with CI | seaborn | `regplot`, `lmplot` |
| Relationship | residuals | seaborn/matplotlib | `residplot` or custom |
| Comparison | bar with error bars | seaborn | `barplot` |
| Comparison | count | seaborn | `countplot` |
| Comparison | heatmap | seaborn | `heatmap` |
| Time Series | line with dates | matplotlib | `plot` + date formatters |
| Statistical | pair plots | seaborn | `pairplot` |
| Statistical | joint plots | seaborn | `jointplot` |
| Custom | annotations, insets | matplotlib | `annotate`, `add_axes` |

## Context7 Integration

When needing documentation for unfamiliar visualization types:

**For matplotlib:**
- resolve-library-id: "matplotlib"
- get-library-docs: query specific functions (e.g., "hexbin", "contourf", "annotate")

**For seaborn:**
- resolve-library-id: "seaborn"
- get-library-docs: query specific functions (e.g., "regplot", "violinplot", "pairplot")

Use context7 when:
- Unfamiliar visualization type requested
- Need to verify function parameters
- Complex customizations needed (colormaps, statistical estimators)
- Uncertain about seaborn vs matplotlib for a specific case

## Interactive Backend Note

All generated functions use `plt.show()` which works with the `macosx` backend for interactive plots. The calling agent should execute with `run_in_background: true` so plots don't block the conversation.
