# Web Accessibility (WCAG 2.1 AA)

**Status**: Production Ready ✅
**Last Updated**: 2026-01-14
**Dependencies**: None (framework-agnostic)
**Standards**: WCAG 2.1 Level AA

---

## Quick Start (5 Minutes)

### 1. Semantic HTML Foundation

Choose the right element - don't use `div` for everything:

```html
<!-- ❌ WRONG - divs with onClick -->
<div onclick="submit()">Submit</div>
<div onclick="navigate()">Next page</div>

<!-- ✅ CORRECT - semantic elements -->
<button type="submit">Submit</button>
<a href="/next">Next page</a>
```

**Why this matters:**
- Semantic elements have built-in keyboard support
- Screen readers announce role automatically
- Browser provides default accessible behaviors

### 2. Focus Management

Make interactive elements keyboard-accessible:

```css
/* ❌ WRONG - removes focus outline */
button:focus { outline: none; }

/* ✅ CORRECT - custom accessible outline */
button:focus-visible {
  outline: 2px solid var(--primary);
  outline-offset: 2px;
}
```

**CRITICAL:**
- Never remove focus outlines without replacement
- Use `:focus-visible` to show only on keyboard focus
- Ensure 3:1 contrast ratio for focus indicators

### 3. Text Alternatives

Every non-text element needs a text alternative:

```html
<!-- ❌ WRONG - no alt text -->
<img src="logo.png">
<button><svg>...</svg></button>

<!-- ✅ CORRECT - proper alternatives -->
<img src="logo.png" alt="Company Name">
<button aria-label="Close dialog"><svg>...</svg></button>
```

---

## The 5-Step Accessibility Process

### Step 1: Choose Semantic HTML

**Decision tree for element selection:**

```
Need clickable element?
├─ Navigates to another page? → <a href="...">
├─ Submits form? → <button type="submit">
├─ Opens dialog? → <button aria-haspopup="dialog">
└─ Other action? → <button type="button">

Grouping content?
├─ Self-contained article? → <article>
├─ Thematic section? → <section>
├─ Navigation links? → <nav>
└─ Supplementary info? → <aside>

Form element?
├─ Text input? → <input type="text">
├─ Multiple choice? → <select> or <input type="radio">
├─ Toggle? → <input type="checkbox"> or <button aria-pressed>
└─ Long text? → <textarea>
```

**See `references/semantic-html.md` for complete guide.**

### Step 2: Add ARIA When Needed

**Golden rule: Use ARIA only when HTML can't express the pattern.**

```html
<!-- ❌ WRONG - unnecessary ARIA -->
<button role="button">Click me</button>  <!-- Button already has role -->

<!-- ✅ CORRECT - ARIA fills semantic gap -->
<div role="dialog" aria-labelledby="title" aria-modal="true">
  <h2 id="title">Confirm action</h2>
  <!-- No HTML dialog yet, so role needed -->
</div>

<!-- ✅ BETTER - Use native HTML when available -->
<dialog aria-labelledby="title">
  <h2 id="title">Confirm action</h2>
</dialog>
```

**Common ARIA patterns:**
- `aria-label` - When visible label doesn't exist
- `aria-labelledby` - Reference existing text as label
- `aria-describedby` - Additional description
- `aria-live` - Announce dynamic updates
- `aria-expanded` - Collapsible/expandable state

**See `references/aria-patterns.md` for complete patterns.**

### Step 3: Implement Keyboard Navigation

**All interactive elements must be keyboard-accessible:**

```typescript
// Tab order management
function Dialog({ onClose }) {
  const dialogRef = useRef<HTMLDivElement>(null);
  const previousFocus = useRef<HTMLElement | null>(null);

  useEffect(() => {
    // Save previous focus
    previousFocus.current = document.activeElement as HTMLElement;

    // Focus first element in dialog
    const firstFocusable = dialogRef.current?.querySelector('button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])');
    (firstFocusable as HTMLElement)?.focus();

    // Trap focus within dialog
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
      if (e.key === 'Tab') {
        // Focus trap logic here
      }
    };

    document.addEventListener('keydown', handleKeyDown);
    return () => {
      document.removeEventListener('keydown', handleKeyDown);
      // Restore focus on close
      previousFocus.current?.focus();
    };
  }, [onClose]);

  return <div ref={dialogRef} role="dialog">...</div>;
}
```

**Essential keyboard patterns:**
- Tab/Shift+Tab: Navigate between focusable elements
- Enter/Space: Activate buttons/links
- Arrow keys: Navigate within components (tabs, menus)
- Escape: Close dialogs/menus
- Home/End: Jump to first/last item

**See `references/focus-management.md` for complete patterns.**

### Step 4: Ensure Color Contrast

**WCAG AA requirements:**
- Normal text (under 18pt): 4.5:1 contrast ratio
- Large text (18pt+ or 14pt+ bold): 3:1 contrast ratio
- UI components (buttons, borders): 3:1 contrast ratio

```css
/* ❌ WRONG - insufficient contrast */
:root {
  --background: #ffffff;
  --text: #999999;  /* 2.8:1 - fails WCAG AA */
}

/* ✅ CORRECT - sufficient contrast */
:root {
  --background: #ffffff;
  --text: #595959;  /* 4.6:1 - passes WCAG AA */
}
```

**Testing tools:**
- Browser DevTools (Chrome/Firefox have built-in checkers)
- Contrast checker extensions
- axe DevTools extension

**See `references/color-contrast.md` for complete guide.**

### Step 5: Make Forms Accessible

**Every form input needs a visible label:**

```html
<!-- ❌ WRONG - placeholder is not a label -->
<input type="email" placeholder="Email address">

<!-- ✅ CORRECT - proper label -->
<label for="email">Email address</label>
<input type="email" id="email" name="email" required aria-required="true">
```

**Error handling:**

```html
<label for="email">Email address</label>
<input
  type="email"
  id="email"
  name="email"
  aria-invalid="true"
  aria-describedby="email-error"
>
<span id="email-error" role="alert">
  Please enter a valid email address
</span>
```

**Live regions for dynamic errors:**

```html
<div role="alert" aria-live="assertive" aria-atomic="true">
  Form submission failed. Please fix the errors above.
</div>
```

**See `references/forms-validation.md` for complete patterns.**

---

## Critical Rules

### Always Do

✅ Use semantic HTML elements first (button, a, nav, article, etc.)
✅ Provide text alternatives for all non-text content
✅ Ensure 4.5:1 contrast for normal text, 3:1 for large text/UI
✅ Make all functionality keyboard accessible
✅ Test with keyboard only (unplug mouse)
✅ Test with screen reader (NVDA on Windows, VoiceOver on Mac)
✅ Use proper heading hierarchy (h1 → h2 → h3, no skipping)
✅ Label all form inputs with visible labels
✅ Provide focus indicators (never just `outline: none`)
✅ Use `aria-live` for dynamic content updates

### Never Do

❌ Use `div` with `onClick` instead of `button`
❌ Remove focus outlines without replacement
❌ Use color alone to convey information
❌ Use placeholders as labels
❌ Skip heading levels (h1 → h3)
❌ Use `tabindex` > 0 (messes with natural order)
❌ Add ARIA when semantic HTML exists
❌ Forget to restore focus after closing dialogs
❌ Use `role="presentation"` on focusable elements
❌ Create keyboard traps (no way to escape)

---

## Known Issues Prevention

This skill prevents **12** documented accessibility issues:

### Issue #1: Missing Focus Indicators

**Error**: Interactive elements have no visible focus indicator
**Source**: WCAG 2.4.7 (Focus Visible)
**Why It Happens**: CSS reset removes default outline
**Prevention**: Always provide custom focus-visible styles

### Issue #2: Insufficient Color Contrast

**Error**: Text has less than 4.5:1 contrast ratio
**Source**: WCAG 1.4.3 (Contrast Minimum)
**Why It Happens**: Using light gray text on white background
**Prevention**: Test all text colors with contrast checker

### Issue #3: Missing Alt Text

**Error**: Images missing alt attributes
**Source**: WCAG 1.1.1 (Non-text Content)
**Why It Happens**: Forgot to add or thought it was optional
**Prevention**: Add alt="" for decorative, descriptive alt for meaningful images

### Issue #4: Keyboard Navigation Broken

**Error**: Interactive elements not reachable by keyboard
**Source**: WCAG 2.1.1 (Keyboard)
**Why It Happens**: Using div onClick instead of button
**Prevention**: Use semantic interactive elements (button, a)

### Issue #5: Form Inputs Without Labels

**Error**: Input fields missing associated labels
**Source**: WCAG 3.3.2 (Labels or Instructions)
**Why It Happens**: Using placeholder as label
**Prevention**: Always use `<label>` element with for/id association

### Issue #6: Skipped Heading Levels

**Error**: Heading hierarchy jumps from h1 to h3
**Source**: WCAG 1.3.1 (Info and Relationships)
**Why It Happens**: Using headings for visual styling instead of semantics
**Prevention**: Use headings in order, style with CSS

### Issue #7: No Focus Trap in Dialogs

**Error**: Tab key exits dialog to background content
**Source**: WCAG 2.4.3 (Focus Order)
**Why It Happens**: No focus trap implementation
**Prevention**: Implement focus trap for modal dialogs

### Issue #8: Missing aria-live for Dynamic Content

**Error**: Screen reader doesn't announce updates
**Source**: WCAG 4.1.3 (Status Messages)
**Why It Happens**: Dynamic content added without announcement
**Prevention**: Use aria-live="polite" or "assertive"

### Issue #9: Color-Only Information

**Error**: Using only color to convey status
**Source**: WCAG 1.4.1 (Use of Color)
**Why It Happens**: Red text for errors without icon/text
**Prevention**: Add icon + text label, not just color

### Issue #10: Non-descriptive Link Text

**Error**: Links with "click here" or "read more"
**Source**: WCAG 2.4.4 (Link Purpose)
**Why It Happens**: Generic link text without context
**Prevention**: Use descriptive link text or aria-label

### Issue #11: Auto-playing Media

**Error**: Video/audio auto-plays without user control
**Source**: WCAG 1.4.2 (Audio Control)
**Why It Happens**: Autoplay attribute without controls
**Prevention**: Require user interaction to start media

### Issue #12: Inaccessible Custom Controls

**Error**: Custom select/checkbox without keyboard support
**Source**: WCAG 4.1.2 (Name, Role, Value)
**Why It Happens**: Building from divs without ARIA
**Prevention**: Use native elements or implement full ARIA pattern

---

## WCAG 2.1 AA Quick Checklist

### Perceivable

- [ ] All images have alt text (or alt="" if decorative)
- [ ] Text contrast ≥ 4.5:1 (normal), ≥ 3:1 (large)
- [ ] Color not used alone to convey information
- [ ] Text can be resized to 200% without loss of content
- [ ] No auto-playing audio >3 seconds

### Operable

- [ ] All functionality keyboard accessible
- [ ] No keyboard traps
- [ ] Visible focus indicators
- [ ] Users can pause/stop/hide moving content
- [ ] Page titles describe purpose
- [ ] Focus order is logical
- [ ] Link purpose clear from text or context
- [ ] Multiple ways to find pages (menu, search, sitemap)
- [ ] Headings and labels describe purpose

### Understandable

- [ ] Page language specified (`<html lang="en">`)
- [ ] Language changes marked (`<span lang="es">`)
- [ ] No unexpected context changes on focus/input
- [ ] Consistent navigation across site
- [ ] Form labels/instructions provided
- [ ] Input errors identified and described
- [ ] Error prevention for legal/financial/data changes

### Robust

- [ ] Valid HTML (no parsing errors)
- [ ] Name, role, value available for all UI components
- [ ] Status messages identified (aria-live)

---

## Testing Workflow

### 1. Keyboard-Only Testing (5 minutes)

```
1. Unplug mouse or hide cursor
2. Tab through entire page
   - Can you reach all interactive elements?
   - Can you activate all buttons/links?
   - Is focus order logical?
3. Use Enter/Space to activate
4. Use Escape to close dialogs
5. Use arrow keys in menus/tabs
```

### 2. Screen Reader Testing (10 minutes)

**NVDA (Windows - Free)**:
- Download: https://www.nvaccess.org/download/
- Start: Ctrl+Alt+N
- Navigate: Arrow keys or Tab
- Read: NVDA+Down arrow
- Stop: NVDA+Q

**VoiceOver (Mac - Built-in)**:
- Start: Cmd+F5
- Navigate: VO+Right/Left arrow (VO = Ctrl+Option)
- Read: VO+A (read all)
- Stop: Cmd+F5

**What to test:**
- Are all interactive elements announced?
- Are images described properly?
- Are form labels read with inputs?
- Are dynamic updates announced?
- Is heading structure clear?

### 3. Automated Testing

**axe DevTools** (Browser extension - highly recommended):
- Install: Chrome/Firefox extension
- Run: F12 → axe DevTools tab → Scan
- Fix: Review violations, follow remediation
- Retest: Scan again after fixes

**Lighthouse** (Built into Chrome):
- Open DevTools (F12)
- Lighthouse tab
- Select "Accessibility" category
- Generate report
- Score 90+ is good, 100 is ideal

---

## Common Patterns

### Pattern 1: Accessible Dialog/Modal

```typescript
interface DialogProps {
  isOpen: boolean;
  onClose: () => void;
  title: string;
  children: React.ReactNode;
}

function Dialog({ isOpen, onClose, title, children }: DialogProps) {
  const dialogRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!isOpen) return;

    const previousFocus = document.activeElement as HTMLElement;

    // Focus first focusable element
    const firstFocusable = dialogRef.current?.querySelector(
      'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
    ) as HTMLElement;
    firstFocusable?.focus();

    // Focus trap
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        onClose();
      }
      if (e.key === 'Tab') {
        const focusableElements = dialogRef.current?.querySelectorAll(
          'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
        );
        if (!focusableElements?.length) return;

        const first = focusableElements[0] as HTMLElement;
        const last = focusableElements[focusableElements.length - 1] as HTMLElement;

        if (e.shiftKey && document.activeElement === first) {
          e.preventDefault();
          last.focus();
        } else if (!e.shiftKey && document.activeElement === last) {
          e.preventDefault();
          first.focus();
        }
      }
    };

    document.addEventListener('keydown', handleKeyDown);

    return () => {
      document.removeEventListener('keydown', handleKeyDown);
      previousFocus?.focus();
    };
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  return (
    <>
      {/* Backdrop */}
      <div
        className="dialog-backdrop"
        onClick={onClose}
        aria-hidden="true"
      />

      {/* Dialog */}
      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="dialog-title"
        className="dialog"
      >
        <h2 id="dialog-title">{title}</h2>
        <div className="dialog-content">{children}</div>
        <button onClick={onClose} aria-label="Close dialog">×</button>
      </div>
    </>
  );
}
```

**When to use**: Any modal dialog or overlay that blocks interaction with background content.

### Pattern 2: Accessible Tabs

```typescript
function Tabs({ tabs }: { tabs: Array<{ label: string; content: React.ReactNode }> }) {
  const [activeIndex, setActiveIndex] = useState(0);

  const handleKeyDown = (e: React.KeyboardEvent, index: number) => {
    if (e.key === 'ArrowLeft') {
      e.preventDefault();
      const newIndex = index === 0 ? tabs.length - 1 : index - 1;
      setActiveIndex(newIndex);
    } else if (e.key === 'ArrowRight') {
      e.preventDefault();
      const newIndex = index === tabs.length - 1 ? 0 : index + 1;
      setActiveIndex(newIndex);
    } else if (e.key === 'Home') {
      e.preventDefault();
      setActiveIndex(0);
    } else if (e.key === 'End') {
      e.preventDefault();
      setActiveIndex(tabs.length - 1);
    }
  };

  return (
    <div>
      <div role="tablist" aria-label="Content tabs">
        {tabs.map((tab, index) => (
          <button
            key={index}
            role="tab"
            aria-selected={activeIndex === index}
            aria-controls={`panel-${index}`}
            id={`tab-${index}`}
            tabIndex={activeIndex === index ? 0 : -1}
            onClick={() => setActiveIndex(index)}
            onKeyDown={(e) => handleKeyDown(e, index)}
          >
            {tab.label}
          </button>
        ))}
      </div>
      {tabs.map((tab, index) => (
        <div
          key={index}
          role="tabpanel"
          id={`panel-${index}`}
          aria-labelledby={`tab-${index}`}
          hidden={activeIndex !== index}
          tabIndex={0}
        >
          {tab.content}
        </div>
      ))}
    </div>
  );
}
```

**When to use**: Tabbed interface with multiple panels.

### Pattern 3: Skip Links

```html
<!-- Place at very top of body -->
<a href="#main-content" class="skip-link">
  Skip to main content
</a>

<style>
.skip-link {
  position: absolute;
  top: -40px;
  left: 0;
  background: var(--primary);
  color: white;
  padding: 8px 16px;
  z-index: 9999;
}

.skip-link:focus {
  top: 0;
}
</style>

<!-- Then in your layout -->
<main id="main-content" tabindex="-1">
  <!-- Page content -->
</main>
```

**When to use**: All multi-page websites with navigation/header before main content.

### Pattern 4: Accessible Form with Validation

```typescript
function ContactForm() {
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [touched, setTouched] = useState<Record<string, boolean>>({});

  const validateEmail = (email: string) => {
    if (!email) return 'Email is required';
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) return 'Email is invalid';
    return '';
  };

  const handleBlur = (field: string, value: string) => {
    setTouched(prev => ({ ...prev, [field]: true }));
    const error = validateEmail(value);
    setErrors(prev => ({ ...prev, [field]: error }));
  };

  return (
    <form>
      <div>
        <label htmlFor="email">Email address *</label>
        <input
          type="email"
          id="email"
          name="email"
          required
          aria-required="true"
          aria-invalid={touched.email && !!errors.email}
          aria-describedby={errors.email ? 'email-error' : undefined}
          onBlur={(e) => handleBlur('email', e.target.value)}
        />
        {touched.email && errors.email && (
          <span id="email-error" role="alert" className="error">
            {errors.email}
          </span>
        )}
      </div>

      <button type="submit">Submit</button>

      {/* Global form error */}
      <div role="alert" aria-live="assertive" aria-atomic="true">
        {/* Dynamic error message appears here */}
      </div>
    </form>
  );
}
```

**When to use**: All forms with validation.

---

## Using Bundled Resources

### References (references/)

Detailed documentation for deep dives:

- **wcag-checklist.md** - Complete WCAG 2.1 Level A & AA requirements with examples
- **semantic-html.md** - Element selection guide, when to use which tag
- **aria-patterns.md** - ARIA roles, states, properties, and when to use them
- **focus-management.md** - Focus order, focus traps, focus restoration patterns
- **color-contrast.md** - Contrast requirements, testing tools, color palette tips
- **forms-validation.md** - Accessible form patterns, error handling, announcements

**When Claude should load these**:
- User asks for complete WCAG checklist
- Deep dive into specific pattern (tabs, accordions, etc.)
- Color contrast issues or palette design
- Complex form validation scenarios

### Agents (agents/)

- **a11y-auditor.md** - Automated accessibility auditor that checks pages for violations

**When to use**: Request accessibility audit of existing page/component.

---

## Advanced Topics

### ARIA Live Regions

Three politeness levels:

```html
<!-- Polite: Wait for screen reader to finish current announcement -->
<div aria-live="polite">New messages: 3</div>

<!-- Assertive: Interrupt immediately -->
<div aria-live="assertive" role="alert">
  Error: Form submission failed
</div>

<!-- Off: Don't announce (default) -->
<div aria-live="off">Loading...</div>
```

**Best practices:**
- Use `polite` for non-critical updates (notifications, counters)
- Use `assertive` for errors and critical alerts
- Use `aria-atomic="true"` to read entire region on change
- Keep messages concise and meaningful

### Focus Management in SPAs

React Router doesn't reset focus on navigation - you need to handle it:

```typescript
function App() {
  const location = useLocation();
  const mainRef = useRef<HTMLElement>(null);

  useEffect(() => {
    // Focus main content on route change
    mainRef.current?.focus();
    // Announce page title to screen readers
    const title = document.title;
    const announcement = document.createElement('div');
    announcement.setAttribute('role', 'status');
    announcement.setAttribute('aria-live', 'polite');
    announcement.textContent = `Navigated to ${title}`;
    document.body.appendChild(announcement);
    setTimeout(() => announcement.remove(), 1000);
  }, [location.pathname]);

  return <main ref={mainRef} tabIndex={-1} id="main-content">...</main>;
}
```

### Accessible Data Tables

```html
<table>
  <caption>Monthly sales by region</caption>
  <thead>
    <tr>
      <th scope="col">Region</th>
      <th scope="col">Q1</th>
      <th scope="col">Q2</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <th scope="row">North</th>
      <td>$10,000</td>
      <td>$12,000</td>
    </tr>
  </tbody>
</table>
```

**Key attributes:**
- `<caption>` - Describes table purpose
- `scope="col"` - Identifies column headers
- `scope="row"` - Identifies row headers
- Associates data cells with headers for screen readers

---

## Official Documentation

- **WCAG 2.1**: https://www.w3.org/WAI/WCAG21/quickref/
- **MDN Accessibility**: https://developer.mozilla.org/en-US/docs/Web/Accessibility
- **ARIA Authoring Practices**: https://www.w3.org/WAI/ARIA/apg/
- **WebAIM**: https://webaim.org/articles/
- **axe DevTools**: https://www.deque.com/axe/devtools/

---

## Troubleshooting

### Problem: Focus indicators not visible

**Symptoms**: Can tab through page but don't see where focus is
**Cause**: CSS removed outlines or insufficient contrast
**Solution**:
```css
*:focus-visible {
  outline: 2px solid var(--primary);
  outline-offset: 2px;
}
```

### Problem: Screen reader not announcing updates

**Symptoms**: Dynamic content changes but no announcement
**Cause**: No aria-live region
**Solution**: Wrap dynamic content in `<div aria-live="polite">` or use role="alert"

### Problem: Dialog focus escapes to background

**Symptoms**: Tab key navigates to elements behind dialog
**Cause**: No focus trap
**Solution**: Implement focus trap (see Pattern 1 above)

### Problem: Form errors not announced

**Symptoms**: Visual errors appear but screen reader doesn't notice
**Cause**: No aria-invalid or role="alert"
**Solution**: Use aria-invalid + aria-describedby pointing to error message with role="alert"

---

## Complete Setup Checklist

Use this for every page/component:

- [ ] All interactive elements are keyboard accessible
- [ ] Visible focus indicators on all focusable elements
- [ ] Images have alt text (or alt="" if decorative)
- [ ] Text contrast ≥ 4.5:1 (test with axe or Lighthouse)
- [ ] Form inputs have associated labels (not just placeholders)
- [ ] Heading hierarchy is logical (no skipped levels)
- [ ] Page has `<html lang="en">` or appropriate language
- [ ] Dialogs have focus trap and restore focus on close
- [ ] Dynamic content uses aria-live or role="alert"
- [ ] Color not used alone to convey information
- [ ] Tested with keyboard only (no mouse)
- [ ] Tested with screen reader (NVDA or VoiceOver)
- [ ] Ran axe DevTools scan (0 violations)
- [ ] Lighthouse accessibility score ≥ 90

---

**Questions? Issues?**

1. Check `references/wcag-checklist.md` for complete requirements
2. Use `/a11y-auditor` agent to scan your page
3. Run axe DevTools for automated testing
4. Test with actual keyboard + screen reader

---

**Standards**: WCAG 2.1 Level AA
**Testing Tools**: axe DevTools, Lighthouse, NVDA, VoiceOver
**Success Criteria**: 90+ Lighthouse score, 0 critical violations


---

# Accessibility Correction Rules

Common accessibility mistakes and their corrections for Claude Code to apply automatically.

---

## Interactive Elements

| If Claude suggests... | Use instead... |
|----------------------|----------------|
| `<div onclick="doThing()">Click</div>` | `<button type="button" onclick="doThing()">Click</button>` |
| `<span onclick="submit()">Submit</span>` | `<button type="submit">Submit</button>` |
| `<a href="#" onclick="doThing()">Action</a>` | `<button type="button" onclick="doThing()">Action</button>` |
| `<a href="javascript:void(0)">Action</a>` | `<button type="button">Action</button>` |
| `<div class="button">Click</div>` | `<button>Click</button>` |

**Why**: Divs and spans are not keyboard accessible and have no semantic role. Use `<button>` for actions, `<a>` only for navigation.

---

## Focus Indicators

| If Claude suggests... | Use instead... |
|----------------------|----------------|
| `*:focus { outline: none; }` | `*:focus-visible { outline: 2px solid var(--primary); outline-offset: 2px; }` |
| `button:focus { outline: 0; }` | `button:focus-visible { outline: 2px solid var(--primary); }` |
| Removing outline without replacement | Always provide custom focus indicator |

**Why**: Focus indicators are required for keyboard navigation. Use `:focus-visible` to show only on keyboard focus.

---

## Images

| If Claude suggests... | Use instead... |
|----------------------|----------------|
| `<img src="logo.png">` | `<img src="logo.png" alt="Company Name">` |
| `<img src="icon.png" alt="">` in button | `<button aria-label="Close"><img src="icon.png" alt=""></button>` |
| `<div style="background-image: url(...)">` for content image | `<img src="..." alt="Description">` |
| Alt text starting with "Image of" | Describe what image conveys, not that it's an image |

**Why**: All images need alt text. Use `alt=""` only for purely decorative images.

---

## Form Labels

| If Claude suggests... | Use instead... |
|----------------------|----------------|
| `<input placeholder="Email">` | `<label for="email">Email</label><input type="email" id="email" placeholder="name@example.com">` |
| `<input aria-label="Email">` | `<label for="email">Email</label><input type="email" id="email">` (prefer visible label) |
| Label without for/id connection | `<label for="email">Email</label><input id="email">` |

**Why**: Placeholders are not labels. Every input needs a visible, associated label.

---

## Headings

| If Claude suggests... | Use instead... |
|----------------------|----------------|
| `<h1>Title</h1><h3>Subtitle</h3>` | `<h1>Title</h1><h2>Subtitle</h2>` (don't skip levels) |
| `<h3 class="big">Title</h3>` for styling | `<h2 class="smaller">Title</h2>` (use correct level + CSS) |
| Multiple `<h1>` on same page | One `<h1>` per page (page title) |

**Why**: Screen readers use heading hierarchy for navigation. Never skip levels.

---

## Color Contrast

| If Claude suggests... | Use instead... |
|----------------------|----------------|
| Light gray `#999` on white background | Darker `#595959` (4.6:1 contrast) or `#737373` (4.7:1) |
| Blue `#4d90fe` on white (2.9:1) | Darker blue `#0066cc` (5.7:1) or `#004080` (6.5:1) |
| Red `#ef4444` on white (3.3:1) | Darker red `#b91c1c` (6.2:1) |
| Color alone for errors | Icon + text + color |

**Why**: WCAG requires 4.5:1 contrast for normal text, 3:1 for large text and UI components.

---

## ARIA Usage

| If Claude suggests... | Use instead... |
|----------------------|----------------|
| `<button role="button">Click</button>` | `<button>Click</button>` (native element already has role) |
| `<div role="button">Click</div>` | `<button>Click</button>` (use native element) |
| aria-label when visible text exists | Use visible text, omit aria-label |
| `<button aria-hidden="true">Click</button>` | Remove aria-hidden (makes button inaccessible) |

**Why**: No ARIA is better than bad ARIA. Use semantic HTML first.

---

## Keyboard Navigation

| If Claude suggests... | Use instead... |
|----------------------|----------------|
| `tabindex="1"` or other positive numbers | `tabindex="0"` or natural order |
| Interactive div without tabindex | `<button>` (natively keyboard accessible) |
| No Escape key handler for dialogs | Add Escape listener to close dialog |
| No focus trap in modals | Implement focus trap pattern |

**Why**: Positive tabindex breaks natural tab order. All interactive elements must be keyboard accessible.

---

## Semantic HTML

| If Claude suggests... | Use instead... |
|----------------------|----------------|
| `<div class="header">` | `<header>` |
| `<div class="nav">` | `<nav>` |
| `<div class="article">` | `<article>` |
| `<div class="section">` | `<section>` (with heading) |
| `<span onclick="...">` for interactive | `<button>` |

**Why**: Semantic elements provide built-in accessibility and structure.

---

## Link Purpose

| If Claude suggests... | Use instead... |
|----------------------|----------------|
| `<a href="/article">Click here</a>` | `<a href="/article">Read our accessibility guide</a>` |
| `<a href="/more">Read more</a>` | `<a href="/article" aria-label="Read more about accessibility">Read more</a>` |
| Generic "Learn more" links | Descriptive link text or aria-label with context |

**Why**: Link text should describe destination. Screen reader users often navigate by links list.

---

## Form Validation

| If Claude suggests... | Use instead... |
|----------------------|----------------|
| Visual error without aria-invalid | `<input aria-invalid="true" aria-describedby="error">` |
| Error message without role="alert" | `<span id="error" role="alert">Error message</span>` |
| No aria-describedby connection | Link input to error via aria-describedby |
| Required field without indicator | `<input required aria-required="true">` + visual indicator |

**Why**: Screen readers need programmatic error indication and connection to error messages.

---

## Live Regions

| If Claude suggests... | Use instead... |
|----------------------|----------------|
| Dynamic content without announcement | `<div aria-live="polite">New content</div>` |
| Critical error without announcement | `<div role="alert">Error message</div>` |
| Status update not announced | `<div role="status">Update</div>` |

**Why**: Screen readers don't automatically announce dynamic content changes.

---

## Tables

| If Claude suggests... | Use instead... |
|----------------------|----------------|
| `<table>` without headers | `<table><thead><tr><th scope="col">Header</th></tr></thead>` |
| Headers without scope attribute | `<th scope="col">` for columns, `<th scope="row">` for rows |
| Table without caption | `<table><caption>Table description</caption>` |

**Why**: Screen readers use headers to associate data cells with their labels.

---

## Skip Links

| If Claude suggests... | Use instead... |
|----------------------|----------------|
| No skip link | `<a href="#main" class="skip-link">Skip to main content</a>` at top of body |
| Skip link always visible | Hide offscreen, show on focus |
| Skip target not focusable | `<main id="main" tabindex="-1">` |

**Why**: Keyboard users need to skip repeated navigation on every page.

---

## Auto-playing Media

| If Claude suggests... | Use instead... |
|----------------------|----------------|
| `<video autoplay>` | `<video controls>` (require user interaction) |
| `<audio autoplay>` | `<audio controls>` |
| Autoplay without pause | Add controls or pause button |

**Why**: Auto-playing media is disruptive for screen reader users.

---

## Language

| If Claude suggests... | Use instead... |
|----------------------|----------------|
| `<html>` without lang | `<html lang="en">` |
| Foreign language phrase without marking | `<span lang="fr">bonjour</span>` |

**Why**: Screen readers need language to pronounce text correctly.

---

## Testing Prompts

When Claude completes accessibility work, always prompt:

```
✅ Completed. Please test:
1. Tab through with keyboard only
2. Run axe DevTools scan
3. Test with screen reader (NVDA or VoiceOver)
4. Verify 4.5:1 contrast on all text
```

---

**Remember**: Accessibility is not optional. These corrections ensure WCAG 2.1 AA compliance and usable interfaces for everyone.



# Color Palette Generation

**Status**: Production Ready ✅
**Last Updated**: 2026-01-14
**Standard**: Tailwind v4 @theme syntax

---

## Quick Start

Generate complete palette from brand hex:

```javascript
// Input: Brand hex
const brandColor = "#0D9488" // Teal-600

// Output: 11-shade scale + semantic tokens + dark mode
primary-50:  #F0FDFA (lightest)
primary-500: #14B8A6 (brand)
primary-950: #042F2E (darkest)

background: #FFFFFF
foreground: #0F172A
primary: #14B8A6
```

Use the reference files to generate shades, map semantics, and check contrast.

---

## Color Scale Overview

### Standard 11-Shade Scale

| Shade | Lightness | Use Case |
|-------|-----------|----------|
| 50 | 97% | Subtle backgrounds |
| 100 | 94% | Hover states |
| 200 | 87% | Borders, dividers |
| 300 | 75% | Disabled states |
| 400 | 62% | Placeholder text |
| 500 | 48% | **Brand color** |
| 600 | 40% | Primary actions |
| 700 | 33% | Hover on primary |
| 800 | 27% | Active states |
| 900 | 20% | Text on light bg |
| 950 | 10% | Darkest accents |

**Key principle**: Shade 500 represents your brand color. Other shades maintain hue/saturation while varying lightness.

---

## Hex to HSL Conversion

Convert brand hex to HSL for shade generation:

```javascript
// Example: #0D9488 → hsl(174, 84%, 29%)
// H (Hue): 174deg
// S (Saturation): 84%
// L (Lightness): 29%
```

Generate shades by keeping hue constant, adjusting lightness:
- Lighter shades (50-400): Reduce saturation slightly
- Mid shades (500-600): Full saturation
- Darker shades (700-950): Full saturation

See `references/shade-generation.md` for conversion formula.

---

## Semantic Token Mapping

Map shade scale to semantic tokens for components:

### Light Mode
```css
--background: white
--foreground: primary-950
--card: white
--card-foreground: primary-900
--muted: primary-50
--muted-foreground: primary-600
--border: primary-200
--primary: primary-600
--primary-foreground: white
```

### Dark Mode
```css
--background: primary-950
--foreground: primary-50
--card: primary-900
--card-foreground: primary-50
--muted: primary-800
--muted-foreground: primary-400
--border: primary-800
--primary: primary-500
--primary-foreground: white
```

**Pattern**: Invert lightness while preserving relationships. See `references/semantic-mapping.md`.

---

## Dark Mode Pattern

Swap light and dark shades:

| Light Mode | Dark Mode |
|------------|-----------|
| 50 (97% L) | 950 (10% L) |
| 100 (94% L) | 900 (20% L) |
| 200 (87% L) | 800 (27% L) |
| 500 (brand) | 500 (brand, slightly brighter) |

**Preserve brand identity**: Keep hue/saturation consistent, only invert lightness.

CSS pattern:
```css
:root {
  --background: white;
  --foreground: hsl(var(--primary-950));
}

.dark {
  --background: hsl(var(--primary-950));
  --foreground: hsl(var(--primary-50));
}
```

---

## Contrast Checking

WCAG minimum ratios:
- **Text (AA)**: 4.5:1 normal, 3:1 large (18px+)
- **UI Elements**: 3:1 (buttons, borders)

Quick check pairs:
- `primary-600` text on `white` background
- `white` text on `primary-600` background
- `primary-900` text on `primary-50` background

**Formula**:
```javascript
contrast = (lighter + 0.05) / (darker + 0.05)
// Where lighter/darker are relative luminance values
```

See `references/contrast-checking.md` for full formula and fix patterns.

---

## Quick Reference

### Generate Complete Palette
1. Convert brand hex to HSL
2. Generate 11 shades (50-950) by varying lightness
3. Map shades to semantic tokens
4. Create dark mode variants (invert lightness)
5. Check contrast for text pairs

### Tailwind v4 Output
Use `@theme` directive:
```css
@theme {
  --color-primary-50: #F0FDFA;
  --color-primary-500: #14B8A6;
  --color-primary-950: #042F2E;

  --color-background: #FFFFFF;
  --color-foreground: var(--color-primary-950);
}
```

### Common Adjustments
- **Too vibrant at light shades**: Reduce saturation by 10-20%
- **Poor contrast on primary**: Use shade 700+ for text
- **Dark mode too dark**: Use shade 900 instead of 950 for backgrounds
- **Brand color too light/dark**: Adjust to shade 500-600 range

---

## Resources

| File | Purpose |
|------|---------|
| `references/shade-generation.md` | Hex→HSL conversion, lightness values |
| `references/semantic-mapping.md` | Token mapping for light/dark modes |
| `references/dark-mode-palette.md` | Inversion patterns, shade swapping |
| `references/contrast-checking.md` | WCAG formulas, quick check table |
| `templates/tailwind-colors.css` | Complete CSS output template |
| `rules/color-palette.md` | Common mistakes and corrections |

---

## Token Efficiency

**Without skill**: ~8-12k tokens trial-and-error for palette generation
**With skill**: ~3-4k tokens using references
**Savings**: ~65%

**Errors prevented**:
- Poor contrast ratios (accessibility violations)
- Inconsistent shade scales
- Broken dark mode (wrong lightness values)
- Raw Tailwind colors instead of semantic tokens
- Missing foreground pairs for backgrounds

---

## Examples

### Brand Color: Teal (#0D9488)
```css
@theme {
  /* Shade scale */
  --color-primary-50: #F0FDFA;
  --color-primary-100: #CCFBF1;
  --color-primary-200: #99F6E4;
  --color-primary-300: #5EEAD4;
  --color-primary-400: #2DD4BF;
  --color-primary-500: #14B8A6;
  --color-primary-600: #0D9488;
  --color-primary-700: #0F766E;
  --color-primary-800: #115E59;
  --color-primary-900: #134E4A;
  --color-primary-950: #042F2E;

  /* Light mode semantics */
  --color-background: #FFFFFF;
  --color-foreground: var(--color-primary-950);
  --color-primary: var(--color-primary-600);
  --color-primary-foreground: #FFFFFF;
}

.dark {
  /* Dark mode overrides */
  --color-background: var(--color-primary-950);
  --color-foreground: var(--color-primary-50);
  --color-primary: var(--color-primary-500);
}
```

### Brand Color: Purple (#7C3AED)
```css
@theme {
  --color-primary-50: #FAF5FF;
  --color-primary-500: #A855F7;
  --color-primary-950: #3B0764;

  --color-background: #FFFFFF;
  --color-foreground: var(--color-primary-950);
  --color-primary: var(--color-primary-600);
}
```

---

**Next Steps**: Use `references/shade-generation.md` to convert your brand hex to HSL and generate the 11-shade scale.


---

# Color Palette Correction Rules

Common mistakes when generating or using color palettes, and how to fix them.

---

## Never Use Raw Tailwind Colors

Use semantic tokens instead of raw Tailwind color classes.

| If Claude suggests... | Use instead... |
|----------------------|----------------|
| `bg-blue-500` | `bg-primary` |
| `text-gray-600` | `text-muted-foreground` |
| `border-slate-200` | `border-border` |
| `bg-green-600` (for success) | Define `--color-success` semantic token |

**Why**: Raw colors break when switching themes, don't adapt to dark mode, and aren't brand-aligned.

**Fix pattern**:
```css
/* Don't hardcode Tailwind colors */
.button { background: #3B82F6; }

/* Use semantic tokens */
.button { background: hsl(var(--color-primary)); }
```

---

## Always Pair Background with Foreground

Every background token must have a paired foreground token.

| If Claude suggests... | Use instead... |
|----------------------|----------------|
| `--color-card` only | `--color-card` + `--color-card-foreground` |
| `bg-primary` with `text-secondary` | `bg-primary` with `text-primary-foreground` |
| Changing background without foreground | Update both in dark mode |

**Why**: Dark mode breaks if foreground doesn't update with background.

**Example failure**:
```css
:root {
  --color-card: #FFFFFF;
  --color-card-foreground: #1E293B; /* Dark text */
}

.dark {
  --color-card: #1E293B; /* Now dark background */
  /* BUG: card-foreground still #1E293B - invisible text! */
}
```

**Fix**:
```css
.dark {
  --color-card: #1E293B;
  --color-card-foreground: #F1F5F9; /* Light text on dark background */
}
```

---

## Always Check Contrast for Text on Primary

Primary button text must meet WCAG AA (4.5:1 for normal text).

| If Claude suggests... | Use instead... |
|----------------------|----------------|
| White text on primary-500 (3.9:1) | White text on primary-600 or darker |
| primary-600 text on white (5.7:1) | primary-700+ for AAA (7:1+) |
| Assuming brand color works for text | Calculate contrast ratio first |

**Quick fix**: If primary button fails contrast, use shade 100-200 darker.

```css
/* Fails AA (3.9:1) */
--color-primary: var(--color-primary-500);
--color-primary-foreground: #FFFFFF;

/* Passes AA (5.7:1) */
--color-primary: var(--color-primary-600);
--color-primary-foreground: #FFFFFF;
```

---

## Always Provide Dark Mode Variants

All color definitions need dark mode overrides.

| If Claude suggests... | Use instead... |
|----------------------|----------------|
| Light mode colors only | Light mode + `.dark` overrides |
| Same shades for light and dark | Inverted shades (50↔950, 100↔900) |
| Primary-600 in both modes | Primary-600 (light), Primary-500 (dark) |

**Pattern**:
```css
@theme {
  /* Light mode */
  --color-background: #FFFFFF;
  --color-foreground: var(--color-primary-950);
  --color-primary: var(--color-primary-600);
}

.dark {
  /* Dark mode - inverted */
  --color-background: var(--color-primary-950);
  --color-foreground: var(--color-primary-50);
  --color-primary: var(--color-primary-500); /* Brighter for visibility */
}
```

---

## Use HSL for Generated Shades

HSL provides better interpolation than RGB/Hex for shade generation.

| If Claude suggests... | Use instead... |
|----------------------|----------------|
| Hex interpolation (manual averaging) | Convert to HSL, vary lightness |
| RGB mixing | HSL with constant hue |
| Random lightness values | Standard scale (97%, 94%, 87%...) |

**Why**: HSL preserves hue and saturation, creating a cohesive scale. RGB mixing shifts hue unpredictably.

**Example**:
```javascript
// Don't mix hex values
const shade100 = averageHex('#0D9488', '#FFFFFF'); // ❌ Hue shifts

// Use HSL with fixed hue
const brand = { h: 174, s: 84, l: 40 }; // #0D9488
const shade100 = { h: 174, s: 67, l: 94 }; // ✅ Same hue, lighter
```

---

## Don't Use Pure Black or Pure White

Off-black and off-white look better and support elevation.

| If Claude suggests... | Use instead... |
|----------------------|----------------|
| `--color-background: #000000` | `--color-background: var(--color-primary-950)` |
| `--color-foreground: #FFFFFF` | `--color-foreground: var(--color-primary-50)` |
| Pure black for dark mode | Shade 950 (10% lightness) |

**Why**:
- Pure black shows OLED smearing
- Pure white is harsh on eyes
- No room for elevation hierarchy

---

## Generate All 11 Shades

Don't skip shades in the scale - all 11 are needed for flexibility.

| If Claude suggests... | Use instead... |
|----------------------|----------------|
| 5-shade scale (100, 300, 500, 700, 900) | Full 11-shade scale (50-950) |
| Custom lightness values | Standard values (97%, 94%, 87%...) |
| Skipping 50 or 950 | Include extremes for backgrounds/text |

**Why**: UI components need full range:
- 50-300: Backgrounds, hover states
- 400-600: Brand colors, primary actions
- 700-950: Text, dark mode backgrounds

---

## Keep Hue Constant Across Shades

All shades should have the same hue value (H in HSL).

| If Claude suggests... | Use instead... |
|----------------------|----------------|
| Shifting hue for lighter shades | Constant hue, vary lightness only |
| "Warmer" lights, "cooler" darks | Same hue throughout |

**Why**: Hue shifts create disjointed palettes that don't feel like one color family.

**Example**:
```css
/* ❌ Wrong - hue shifts */
--color-primary-50: hsl(180, 70%, 97%);  /* Shifted to blue-green */
--color-primary-600: hsl(174, 84%, 40%); /* Original teal */

/* ✅ Correct - constant hue */
--color-primary-50: hsl(174, 67%, 97%);  /* Same 174deg hue */
--color-primary-600: hsl(174, 84%, 40%);
```

---

## Reduce Saturation for Light Shades

Lighter shades (50-200) should have reduced saturation to avoid garish pastels.

| If Claude suggests... | Use instead... |
|----------------------|----------------|
| Full saturation for shade 50 | Reduce by 15-20% |
| Same saturation for all shades | Gradient: less for lights, full for darks |

**Pattern**:
```javascript
const baseSaturation = 84; // Brand color saturation

// Shade 50 (97% lightness)
const shade50Saturation = baseSaturation * 0.8; // 67%

// Shade 600 (40% lightness)
const shade600Saturation = baseSaturation; // 84% (full)
```

---

## Don't Override Semantic Tokens in Components

Semantic tokens should be defined globally, not overridden per component.

| If Claude suggests... | Use instead... |
|----------------------|----------------|
| `.card { --color-primary: #123456; }` | Use a different semantic token |
| Component-specific color overrides | Global semantic tokens |

**Why**: Overrides break theme consistency and make dark mode unpredictable.

**Fix**: If component needs different color, define new semantic token:
```css
@theme {
  --color-primary: var(--color-primary-600);
  --color-accent: var(--color-accent-500); /* For special components */
}
```

---

## Test Dark Mode Before Finalizing

Always verify dark mode works before committing colors.

| If Claude suggests... | Use instead... |
|----------------------|----------------|
| Testing light mode only | Test both light and dark modes |
| Assuming inversion works | Manually verify each token pair |

**Checklist**:
- [ ] Toggle dark mode and visually inspect
- [ ] Check text readability (no eye strain)
- [ ] Verify buttons/CTAs stand out
- [ ] Test focus rings are visible
- [ ] Check borders aren't too harsh or invisible
- [ ] Verify contrast ratios (WebAIM tool)

---

## Use Semantic Names, Not Descriptive

Token names should describe purpose, not appearance.

| If Claude suggests... | Use instead... |
|----------------------|----------------|
| `--color-light-gray` | `--color-muted` |
| `--color-dark-teal` | `--color-primary` |
| `--color-bright-blue` | `--color-accent` |

**Why**: Descriptive names break when theme changes (dark mode makes "light-gray" dark).

---

## Don't Mix Color Systems

Use one color system consistently (HSL recommended for Tailwind v4).

| If Claude suggests... | Use instead... |
|----------------------|----------------|
| Mix of hex, RGB, HSL | HSL for all custom colors |
| `oklch()` for some, `hsl()` for others | Pick one system |

**Recommendation**: Use HSL for:
- Better human readability
- Easier shade generation
- Tailwind v4 compatibility

**Exception**: Use `oklch()` if perceptual uniformity is critical (advanced use cases).

---

## Summary of Rules

1. ✅ Use semantic tokens, not raw Tailwind colors
2. ✅ Pair every background with a foreground
3. ✅ Check contrast ratios (4.5:1 for text)
4. ✅ Provide dark mode overrides
5. ✅ Use HSL for shade generation
6. ✅ Avoid pure black/white
7. ✅ Generate all 11 shades (50-950)
8. ✅ Keep hue constant across shades
9. ✅ Reduce saturation for light shades
10. ✅ Test dark mode before finalizing

**Prioritize accessibility and consistency over brand purity.**



# Design System Starter

Build robust, scalable design systems that ensure visual consistency and exceptional user experiences.

---

## Quick Start

Just describe what you need:

```
Create a design system for my React app with dark mode support
```

That's it. The skill provides tokens, components, and accessibility guidelines.

---

## Triggers

| Trigger | Example |
|---------|---------|
| Create design system | "Create a design system for my app" |
| Design tokens | "Set up design tokens for colors and spacing" |
| Component architecture | "Design component structure using atomic design" |
| Accessibility | "Ensure WCAG 2.1 compliance for my components" |
| Dark mode | "Implement theming with dark mode support" |

---

## Quick Reference

| Task | Output |
|------|--------|
| Design tokens | Color, typography, spacing, shadows JSON |
| Component structure | Atomic design hierarchy (atoms, molecules, organisms) |
| Theming | CSS variables or ThemeProvider setup |
| Accessibility | WCAG 2.1 AA compliant patterns |
| Documentation | Component docs with props, examples, a11y notes |

---

## Bundled Resources

- `references/component-examples.md` - Complete component implementations
- `templates/design-tokens-template.json` - W3C design token format
- `templates/component-template.tsx` - React component template
- `checklists/design-system-checklist.md` - Design system audit checklist

---

## Design System Philosophy

### What is a Design System?

A design system is more than a component library—it's a collection of:

1. **Design Tokens**: Foundational design decisions (colors, spacing, typography)
2. **Components**: Reusable UI building blocks
3. **Patterns**: Common UX solutions and compositions
4. **Guidelines**: Rules, principles, and best practices
5. **Documentation**: How to use everything effectively

### Core Principles

**1. Consistency Over Creativity**
- Predictable patterns reduce cognitive load
- Users learn once, apply everywhere
- Designers and developers speak the same language

**2. Accessible by Default**
- WCAG 2.1 Level AA compliance minimum
- Keyboard navigation built-in
- Screen reader support from the start

**3. Scalable and Maintainable**
- Design tokens enable global changes
- Component composition reduces duplication
- Versioning and deprecation strategies

**4. Developer-Friendly**
- Clear API contracts
- Comprehensive documentation
- Easy to integrate and customize

---

## Design Tokens

Design tokens are the atomic design decisions that define your system's visual language.

### Token Categories

#### 1. Color Tokens

**Primitive Colors** (Raw values):
```json
{
  "color": {
    "primitive": {
      "blue": {
        "50": "#eff6ff",
        "100": "#dbeafe",
        "200": "#bfdbfe",
        "300": "#93c5fd",
        "400": "#60a5fa",
        "500": "#3b82f6",
        "600": "#2563eb",
        "700": "#1d4ed8",
        "800": "#1e40af",
        "900": "#1e3a8a",
        "950": "#172554"
      }
    }
  }
}
```

**Semantic Colors** (Contextual meaning):
```json
{
  "color": {
    "semantic": {
      "brand": {
        "primary": "{color.primitive.blue.600}",
        "primary-hover": "{color.primitive.blue.700}",
        "primary-active": "{color.primitive.blue.800}"
      },
      "text": {
        "primary": "{color.primitive.gray.900}",
        "secondary": "{color.primitive.gray.600}",
        "tertiary": "{color.primitive.gray.500}",
        "disabled": "{color.primitive.gray.400}",
        "inverse": "{color.primitive.white}"
      },
      "background": {
        "primary": "{color.primitive.white}",
        "secondary": "{color.primitive.gray.50}",
        "tertiary": "{color.primitive.gray.100}"
      },
      "feedback": {
        "success": "{color.primitive.green.600}",
        "warning": "{color.primitive.yellow.600}",
        "error": "{color.primitive.red.600}",
        "info": "{color.primitive.blue.600}"
      }
    }
  }
}
```

**Accessibility**: Ensure color contrast ratios meet WCAG 2.1 Level AA:
- Normal text: 4.5:1 minimum
- Large text (18pt+ or 14pt+ bold): 3:1 minimum
- UI components and graphics: 3:1 minimum

#### 2. Typography Tokens

```json
{
  "typography": {
    "fontFamily": {
      "sans": "'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif",
      "serif": "'Georgia', 'Times New Roman', serif",
      "mono": "'Fira Code', 'Courier New', monospace"
    },
    "fontSize": {
      "xs": "0.75rem",     // 12px
      "sm": "0.875rem",    // 14px
      "base": "1rem",      // 16px
      "lg": "1.125rem",    // 18px
      "xl": "1.25rem",     // 20px
      "2xl": "1.5rem",     // 24px
      "3xl": "1.875rem",   // 30px
      "4xl": "2.25rem",    // 36px
      "5xl": "3rem"        // 48px
    },
    "fontWeight": {
      "normal": 400,
      "medium": 500,
      "semibold": 600,
      "bold": 700
    },
    "lineHeight": {
      "tight": 1.25,
      "normal": 1.5,
      "relaxed": 1.75,
      "loose": 2
    },
    "letterSpacing": {
      "tight": "-0.025em",
      "normal": "0",
      "wide": "0.025em"
    }
  }
}
```

#### 3. Spacing Tokens

**Scale**: Use a consistent spacing scale (commonly 4px or 8px base)

```json
{
  "spacing": {
    "0": "0",
    "1": "0.25rem",   // 4px
    "2": "0.5rem",    // 8px
    "3": "0.75rem",   // 12px
    "4": "1rem",      // 16px
    "5": "1.25rem",   // 20px
    "6": "1.5rem",    // 24px
    "8": "2rem",      // 32px
    "10": "2.5rem",   // 40px
    "12": "3rem",     // 48px
    "16": "4rem",     // 64px
    "20": "5rem",     // 80px
    "24": "6rem"      // 96px
  }
}
```

**Component-Specific Spacing**:
```json
{
  "component": {
    "button": {
      "padding-x": "{spacing.4}",
      "padding-y": "{spacing.2}",
      "gap": "{spacing.2}"
    },
    "card": {
      "padding": "{spacing.6}",
      "gap": "{spacing.4}"
    }
  }
}
```

#### 4. Border Radius Tokens

```json
{
  "borderRadius": {
    "none": "0",
    "sm": "0.125rem",   // 2px
    "base": "0.25rem",  // 4px
    "md": "0.375rem",   // 6px
    "lg": "0.5rem",     // 8px
    "xl": "0.75rem",    // 12px
    "2xl": "1rem",      // 16px
    "full": "9999px"
  }
}
```

#### 5. Shadow Tokens

```json
{
  "shadow": {
    "xs": "0 1px 2px 0 rgba(0, 0, 0, 0.05)",
    "sm": "0 1px 3px 0 rgba(0, 0, 0, 0.1), 0 1px 2px -1px rgba(0, 0, 0, 0.1)",
    "base": "0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -2px rgba(0, 0, 0, 0.1)",
    "md": "0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -4px rgba(0, 0, 0, 0.1)",
    "lg": "0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 8px 10px -6px rgba(0, 0, 0, 0.1)",
    "xl": "0 25px 50px -12px rgba(0, 0, 0, 0.25)"
  }
}
```

---

## Component Architecture

### Atomic Design Methodology

**Atoms** → **Molecules** → **Organisms** → **Templates** → **Pages**

#### Atoms (Primitive Components)
Basic building blocks that can't be broken down further.

**Examples:**
- Button
- Input
- Label
- Icon
- Badge
- Avatar

**Button Component:**
```typescript
interface ButtonProps {
  variant?: 'primary' | 'secondary' | 'outline' | 'ghost';
  size?: 'sm' | 'md' | 'lg';
  disabled?: boolean;
  loading?: boolean;
  icon?: React.ReactNode;
  children: React.ReactNode;
}
```

See `references/component-examples.md` for complete Button implementation with variants, sizes, and styling patterns.

#### Molecules (Simple Compositions)
Groups of atoms that function together.

**Examples:**
- SearchBar (Input + Button)
- FormField (Label + Input + ErrorMessage)
- Card (Container + Title + Content + Actions)

**FormField Molecule:**
```typescript
interface FormFieldProps {
  label: string;
  name: string;
  error?: string;
  hint?: string;
  required?: boolean;
  children: React.ReactNode;
}
```

See `references/component-examples.md` for FormField, Card (compound component pattern), Input with variants, Modal, and more composition examples.

#### Organisms (Complex Compositions)
Complex UI components made of molecules and atoms.

**Examples:**
- Navigation Bar
- Product Card Grid
- User Profile Section
- Modal Dialog

#### Templates (Page Layouts)
Page-level structures that define content placement.

**Examples:**
- Dashboard Layout (Sidebar + Header + Main Content)
- Marketing Page Layout (Hero + Features + Footer)
- Settings Page Layout (Tabs + Content Panels)

#### Pages (Specific Instances)
Actual pages with real content.

---

## Component API Design

### Props Best Practices

**1. Predictable Prop Names**
```typescript
// ✅ Good: Consistent naming
<Button variant="primary" size="md" />
<Input variant="outlined" size="md" />

// ❌ Bad: Inconsistent
<Button type="primary" sizeMode="md" />
<Input style="outlined" inputSize="md" />
```

**2. Sensible Defaults**
```typescript
// ✅ Good: Provides defaults
interface ButtonProps {
  variant?: 'primary' | 'secondary';  // Default: primary
  size?: 'sm' | 'md' | 'lg';          // Default: md
}

// ❌ Bad: Everything required
interface ButtonProps {
  variant: 'primary' | 'secondary';
  size: 'sm' | 'md' | 'lg';
  color: string;
  padding: string;
}
```

**3. Composition Over Configuration**
```typescript
// ✅ Good: Composable
<Card>
  <Card.Header>
    <Card.Title>Title</Card.Title>
  </Card.Header>
  <Card.Body>Content</Card.Body>
  <Card.Footer>Actions</Card.Footer>
</Card>

// ❌ Bad: Too many props
<Card
  title="Title"
  content="Content"
  footerContent="Actions"
  hasHeader={true}
  hasFooter={true}
/>
```

**4. Polymorphic Components**
Allow components to render as different HTML elements:
```typescript
<Button as="a" href="/login">Login</Button>
<Button as="button" onClick={handleClick}>Click Me</Button>
```

See `references/component-examples.md` for complete polymorphic component TypeScript patterns.

---

## Theming and Dark Mode

### Theme Structure

```typescript
interface Theme {
  colors: {
    brand: {
      primary: string;
      secondary: string;
    };
    text: {
      primary: string;
      secondary: string;
    };
    background: {
      primary: string;
      secondary: string;
    };
    feedback: {
      success: string;
      warning: string;
      error: string;
      info: string;
    };
  };
  typography: {
    fontFamily: {
      sans: string;
      mono: string;
    };
    fontSize: Record<string, string>;
  };
  spacing: Record<string, string>;
  borderRadius: Record<string, string>;
  shadow: Record<string, string>;
}
```

### Dark Mode Implementation

**Approach 1: CSS Variables**
```css
:root {
  --color-bg-primary: #ffffff;
  --color-text-primary: #000000;
}

[data-theme="dark"] {
  --color-bg-primary: #1a1a1a;
  --color-text-primary: #ffffff;
}
```

**Approach 2: Tailwind CSS Dark Mode**
```tsx
<div className="bg-white dark:bg-gray-900 text-gray-900 dark:text-white">
  Content
</div>
```

**Approach 3: Styled Components ThemeProvider**
```typescript
const lightTheme = { background: '#fff', text: '#000' };
const darkTheme = { background: '#000', text: '#fff' };

<ThemeProvider theme={isDark ? darkTheme : lightTheme}>
  <App />
</ThemeProvider>
```

---

## Accessibility Guidelines

### WCAG 2.1 Level AA Compliance

#### Color Contrast
- **Normal text** (< 18pt): 4.5:1 minimum
- **Large text** (≥ 18pt or ≥ 14pt bold): 3:1 minimum
- **UI components**: 3:1 minimum

**Tools**: Use contrast checkers like [WebAIM Contrast Checker](https://webaim.org/resources/contrastchecker/)

#### Keyboard Navigation
```typescript
// ✅ All interactive elements must be keyboard accessible
<button
  onClick={handleClick}
  onKeyDown={(e) => e.key === 'Enter' && handleClick()}
>
  Click me
</button>

// ✅ Focus management
<Modal>
  <FocusTrap>
    {/* Modal content */}
  </FocusTrap>
</Modal>
```

#### ARIA Attributes
Essential ARIA patterns:
- `aria-label`: Provide accessible names
- `aria-expanded`: Communicate expanded/collapsed state
- `aria-controls`: Associate controls with content
- `aria-live`: Announce dynamic content changes

#### Screen Reader Support
- Use semantic HTML elements (`<button>`, `<nav>`, `<main>`)
- Avoid div/span soup for interactive elements
- Provide meaningful labels for all controls

See `references/component-examples.md` for complete accessibility examples including Skip Links, focus traps, and ARIA patterns.

---

## Documentation Standards

### Component Documentation Template

Each component should document:
- **Purpose**: What the component does
- **Usage**: Import statement and basic example
- **Variants**: Available visual styles
- **Props**: Complete prop table with types, defaults, descriptions
- **Accessibility**: Keyboard support, ARIA attributes, screen reader behavior
- **Examples**: Common use cases with code

Use Storybook, Docusaurus, or similar tools for interactive documentation.

See `templates/component-template.tsx` for the standard component structure.

---

## Design System Workflow

### 1. Design Phase
- **Audit existing patterns**: Identify inconsistencies
- **Define design tokens**: Colors, typography, spacing
- **Create component inventory**: List all needed components
- **Design in Figma**: Create component library

### 2. Development Phase
- **Set up tooling**: Storybook, TypeScript, testing
- **Implement tokens**: CSS variables or theme config
- **Build atoms first**: Start with primitives
- **Compose upward**: Build molecules, organisms
- **Document as you go**: Write docs alongside code

### 3. Adoption Phase
- **Create migration guide**: Help teams adopt
- **Provide codemods**: Automate migrations when possible
- **Run workshops**: Train teams on usage
- **Gather feedback**: Iterate based on real usage

### 4. Maintenance Phase
- **Version semantically**: Major/minor/patch releases
- **Deprecation strategy**: Phase out old components gracefully
- **Changelog**: Document all changes
- **Monitor adoption**: Track usage across products

---

This skill guides creation of distinctive, production-grade frontend interfaces that avoid generic "AI slop" aesthetics. Implement real working code with exceptional attention to aesthetic details and creative choices.

The user provides frontend requirements: a component, page, application, or interface to build. They may include context about the purpose, audience, or technical constraints.

## Design Thinking

Before coding, understand the context and commit to a BOLD aesthetic direction:
- **Purpose**: What problem does this interface solve? Who uses it?
- **Tone**: Pick an extreme: brutally minimal, maximalist chaos, retro-futuristic, organic/natural, luxury/refined, playful/toy-like, editorial/magazine, brutalist/raw, art deco/geometric, soft/pastel, industrial/utilitarian, etc. There are so many flavors to choose from. Use these for inspiration but design one that is true to the aesthetic direction.
- **Constraints**: Technical requirements (framework, performance, accessibility).
- **Differentiation**: What makes this UNFORGETTABLE? What's the one thing someone will remember?

**CRITICAL**: Choose a clear conceptual direction and execute it with precision. Bold maximalism and refined minimalism both work - the key is intentionality, not intensity.

Then implement working code (HTML/CSS/JS, React, Vue, etc.) that is:
- Production-grade and functional
- Visually striking and memorable
- Cohesive with a clear aesthetic point-of-view
- Meticulously refined in every detail

## Frontend Aesthetics Guidelines

Focus on:
- **Typography**: Choose fonts that are beautiful, unique, and interesting. Avoid generic fonts like Arial and Inter; opt instead for distinctive choices that elevate the frontend's aesthetics; unexpected, characterful font choices. Pair a distinctive display font with a refined body font.
- **Color & Theme**: Commit to a cohesive aesthetic. Use CSS variables for consistency. Dominant colors with sharp accents outperform timid, evenly-distributed palettes.
- **Motion**: Use animations for effects and micro-interactions. Prioritize CSS-only solutions for HTML. Use Motion library for React when available. Focus on high-impact moments: one well-orchestrated page load with staggered reveals (animation-delay) creates more delight than scattered micro-interactions. Use scroll-triggering and hover states that surprise.
- **Spatial Composition**: Unexpected layouts. Asymmetry. Overlap. Diagonal flow. Grid-breaking elements. Generous negative space OR controlled density.
- **Backgrounds & Visual Details**: Create atmosphere and depth rather than defaulting to solid colors. Add contextual effects and textures that match the overall aesthetic. Apply creative forms like gradient meshes, noise textures, geometric patterns, layered transparencies, dramatic shadows, decorative borders, custom cursors, and grain overlays.

NEVER use generic AI-generated aesthetics like overused font families (Inter, Roboto, Arial, system fonts), cliched color schemes (particularly purple gradients on white backgrounds), predictable layouts and component patterns, and cookie-cutter design that lacks context-specific character.

Interpret creatively and make unexpected choices that feel genuinely designed for the context. No design should be the same. Vary between light and dark themes, different fonts, different aesthetics. NEVER converge on common choices (Space Grotesk, for example) across generations.

**IMPORTANT**: Match implementation complexity to the aesthetic vision. Maximalist designs need elaborate code with extensive animations and effects. Minimalist or refined designs need restraint, precision, and careful attention to spacing, typography, and subtle details. Elegance comes from executing the vision well.

Remember: Claude is capable of extraordinary creative work. Don't hold back, show what can truly be created when thinking outside the box and committing fully to a distinctive vision.



# Interaction Design

Create engaging, intuitive interactions through motion, feedback, and thoughtful state transitions that enhance usability and delight users.

## When to Use This Skill

- Adding microinteractions to enhance user feedback
- Implementing smooth page and component transitions
- Designing loading states and skeleton screens
- Creating gesture-based interactions
- Building notification and toast systems
- Implementing drag-and-drop interfaces
- Adding scroll-triggered animations
- Designing hover and focus states

## Core Principles

### 1. Purposeful Motion

Motion should communicate, not decorate:

- **Feedback**: Confirm user actions occurred
- **Orientation**: Show where elements come from/go to
- **Focus**: Direct attention to important changes
- **Continuity**: Maintain context during transitions

### 2. Timing Guidelines

| Duration  | Use Case                                  |
| --------- | ----------------------------------------- |
| 100-150ms | Micro-feedback (hovers, clicks)           |
| 200-300ms | Small transitions (toggles, dropdowns)    |
| 300-500ms | Medium transitions (modals, page changes) |
| 500ms+    | Complex choreographed animations          |

### 3. Easing Functions

```css
/* Common easings */
--ease-out: cubic-bezier(0.16, 1, 0.3, 1); /* Decelerate - entering */
--ease-in: cubic-bezier(0.55, 0, 1, 0.45); /* Accelerate - exiting */
--ease-in-out: cubic-bezier(0.65, 0, 0.35, 1); /* Both - moving between */
--spring: cubic-bezier(0.34, 1.56, 0.64, 1); /* Overshoot - playful */
```

## Quick Start: Button Microinteraction

```tsx
import { motion } from "framer-motion";

export function InteractiveButton({ children, onClick }) {
  return (
    <motion.button
      onClick={onClick}
      whileHover={{ scale: 1.02 }}
      whileTap={{ scale: 0.98 }}
      transition={{ type: "spring", stiffness: 400, damping: 17 }}
      className="px-4 py-2 bg-blue-600 text-white rounded-lg"
    >
      {children}
    </motion.button>
  );
}
```

## Interaction Patterns

### 1. Loading States

**Skeleton Screens**: Preserve layout while loading

```tsx
function CardSkeleton() {
  return (
    <div className="animate-pulse">
      <div className="h-48 bg-gray-200 rounded-lg" />
      <div className="mt-4 h-4 bg-gray-200 rounded w-3/4" />
      <div className="mt-2 h-4 bg-gray-200 rounded w-1/2" />
    </div>
  );
}
```

**Progress Indicators**: Show determinate progress

```tsx
function ProgressBar({ progress }: { progress: number }) {
  return (
    <div className="h-2 bg-gray-200 rounded-full overflow-hidden">
      <motion.div
        className="h-full bg-blue-600"
        initial={{ width: 0 }}
        animate={{ width: `${progress}%` }}
        transition={{ ease: "easeOut" }}
      />
    </div>
  );
}
```

### 2. State Transitions

**Toggle with smooth transition**:

```tsx
function Toggle({ checked, onChange }) {
  return (
    <button
      role="switch"
      aria-checked={checked}
      onClick={() => onChange(!checked)}
      className={`
        relative w-12 h-6 rounded-full transition-colors duration-200
        ${checked ? "bg-blue-600" : "bg-gray-300"}
      `}
    >
      <motion.span
        className="absolute top-1 left-1 w-4 h-4 bg-white rounded-full shadow"
        animate={{ x: checked ? 24 : 0 }}
        transition={{ type: "spring", stiffness: 500, damping: 30 }}
      />
    </button>
  );
}
```

### 3. Page Transitions

**Framer Motion layout animations**:

```tsx
import { AnimatePresence, motion } from "framer-motion";

function PageTransition({ children, key }) {
  return (
    <AnimatePresence mode="wait">
      <motion.div
        key={key}
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        exit={{ opacity: 0, y: -20 }}
        transition={{ duration: 0.3 }}
      >
        {children}
      </motion.div>
    </AnimatePresence>
  );
}
```

### 4. Feedback Patterns

**Ripple effect on click**:

```tsx
function RippleButton({ children, onClick }) {
  const [ripples, setRipples] = useState([]);

  const handleClick = (e) => {
    const rect = e.currentTarget.getBoundingClientRect();
    const ripple = {
      x: e.clientX - rect.left,
      y: e.clientY - rect.top,
      id: Date.now(),
    };
    setRipples((prev) => [...prev, ripple]);
    setTimeout(() => {
      setRipples((prev) => prev.filter((r) => r.id !== ripple.id));
    }, 600);
    onClick?.(e);
  };

  return (
    <button onClick={handleClick} className="relative overflow-hidden">
      {children}
      {ripples.map((ripple) => (
        <span
          key={ripple.id}
          className="absolute bg-white/30 rounded-full animate-ripple"
          style={{ left: ripple.x, top: ripple.y }}
        />
      ))}
    </button>
  );
}
```

### 5. Gesture Interactions

**Swipe to dismiss**:

```tsx
function SwipeCard({ children, onDismiss }) {
  return (
    <motion.div
      drag="x"
      dragConstraints={{ left: 0, right: 0 }}
      onDragEnd={(_, info) => {
        if (Math.abs(info.offset.x) > 100) {
          onDismiss();
        }
      }}
      className="cursor-grab active:cursor-grabbing"
    >
      {children}
    </motion.div>
  );
}
```

## CSS Animation Patterns

### Keyframe Animations

```css
@keyframes fadeIn {
  from {
    opacity: 0;
    transform: translateY(10px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

@keyframes pulse {
  0%,
  100% {
    opacity: 1;
  }
  50% {
    opacity: 0.5;
  }
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

.animate-fadeIn {
  animation: fadeIn 0.3s ease-out;
}
.animate-pulse {
  animation: pulse 2s ease-in-out infinite;
}
.animate-spin {
  animation: spin 1s linear infinite;
}
```

### CSS Transitions

```css
.card {
  transition:
    transform 0.2s ease-out,
    box-shadow 0.2s ease-out;
}

.card:hover {
  transform: translateY(-4px);
  box-shadow: 0 12px 24px rgba(0, 0, 0, 0.1);
}
```

## Accessibility Considerations

```css
/* Respect user motion preferences */
@media (prefers-reduced-motion: reduce) {
  *,
  *::before,
  *::after {
    animation-duration: 0.01ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: 0.01ms !important;
  }
}
```

```tsx
function AnimatedComponent() {
  const prefersReducedMotion = window.matchMedia(
    "(prefers-reduced-motion: reduce)",
  ).matches;

  return (
    <motion.div
      animate={{ opacity: 1 }}
      transition={{ duration: prefersReducedMotion ? 0 : 0.3 }}
    />
  );
}
```

## Best Practices

1. **Performance First**: Use `transform` and `opacity` for smooth 60fps
2. **Reduce Motion Support**: Always respect `prefers-reduced-motion`
3. **Consistent Timing**: Use a timing scale across the app
4. **Natural Physics**: Prefer spring animations over linear
5. **Interruptible**: Allow users to cancel long animations
6. **Progressive Enhancement**: Work without JS animations
7. **Test on Devices**: Performance varies significantly

## Common Issues

- **Janky Animations**: Avoid animating `width`, `height`, `top`, `left`
- **Over-animation**: Too much motion causes fatigue
- **Blocking Interactions**: Never prevent user input during animations
- **Memory Leaks**: Clean up animation listeners on unmount
- **Flash of Content**: Use `will-change` sparingly for optimization

## Resources

- [Framer Motion Documentation](https://www.framer.com/motion/)
- [CSS Animation Guide](https://web.dev/animations-guide/)
- [Material Design Motion](https://m3.material.io/styles/motion/overview)
- [GSAP Animation Library](https://greensock.com/gsap/)




# Responsive Design

Master modern responsive design techniques to create interfaces that adapt seamlessly across all screen sizes and device contexts.

## When to Use This Skill

- Implementing mobile-first responsive layouts
- Using container queries for component-based responsiveness
- Creating fluid typography and spacing scales
- Building complex layouts with CSS Grid and Flexbox
- Designing breakpoint strategies for design systems
- Implementing responsive images and media
- Creating adaptive navigation patterns
- Building responsive tables and data displays

## Core Capabilities

### 1. Container Queries

- Component-level responsiveness independent of viewport
- Container query units (cqi, cqw, cqh)
- Style queries for conditional styling
- Fallbacks for browser support

### 2. Fluid Typography & Spacing

- CSS clamp() for fluid scaling
- Viewport-relative units (vw, vh, dvh)
- Fluid type scales with min/max bounds
- Responsive spacing systems

### 3. Layout Patterns

- CSS Grid for 2D layouts
- Flexbox for 1D distribution
- Intrinsic layouts (content-based sizing)
- Subgrid for nested grid alignment

### 4. Breakpoint Strategy

- Mobile-first media queries
- Content-based breakpoints
- Design token integration
- Feature queries (@supports)

## Quick Reference

### Modern Breakpoint Scale

```css
/* Mobile-first breakpoints */
/* Base: Mobile (< 640px) */
@media (min-width: 640px) {
  /* sm: Landscape phones, small tablets */
}
@media (min-width: 768px) {
  /* md: Tablets */
}
@media (min-width: 1024px) {
  /* lg: Laptops, small desktops */
}
@media (min-width: 1280px) {
  /* xl: Desktops */
}
@media (min-width: 1536px) {
  /* 2xl: Large desktops */
}

/* Tailwind CSS equivalent */
/* sm:  @media (min-width: 640px) */
/* md:  @media (min-width: 768px) */
/* lg:  @media (min-width: 1024px) */
/* xl:  @media (min-width: 1280px) */
/* 2xl: @media (min-width: 1536px) */
```

## Key Patterns

### Pattern 1: Container Queries

```css
/* Define a containment context */
.card-container {
  container-type: inline-size;
  container-name: card;
}

/* Query the container, not the viewport */
@container card (min-width: 400px) {
  .card {
    display: grid;
    grid-template-columns: 200px 1fr;
    gap: 1rem;
  }

  .card-image {
    aspect-ratio: 1;
  }
}

@container card (min-width: 600px) {
  .card {
    grid-template-columns: 250px 1fr;
  }

  .card-title {
    font-size: 1.5rem;
  }
}

/* Container query units */
.card-title {
  /* 5% of container width, clamped between 1rem and 2rem */
  font-size: clamp(1rem, 5cqi, 2rem);
}
```

```tsx
// React component with container queries
function ResponsiveCard({ title, image, description }) {
  return (
    <div className="@container">
      <article className="flex flex-col @md:flex-row @md:gap-4">
        <img
          src={image}
          alt=""
          className="w-full @md:w-48 @lg:w-64 aspect-video @md:aspect-square object-cover"
        />
        <div className="p-4 @md:p-0">
          <h2 className="text-lg @md:text-xl @lg:text-2xl font-semibold">
            {title}
          </h2>
          <p className="mt-2 text-muted-foreground @md:line-clamp-3">
            {description}
          </p>
        </div>
      </article>
    </div>
  );
}
```

### Pattern 2: Fluid Typography

```css
/* Fluid type scale using clamp() */
:root {
  /* Min size, preferred (fluid), max size */
  --text-xs: clamp(0.75rem, 0.7rem + 0.25vw, 0.875rem);
  --text-sm: clamp(0.875rem, 0.8rem + 0.375vw, 1rem);
  --text-base: clamp(1rem, 0.9rem + 0.5vw, 1.125rem);
  --text-lg: clamp(1.125rem, 1rem + 0.625vw, 1.25rem);
  --text-xl: clamp(1.25rem, 1rem + 1.25vw, 1.5rem);
  --text-2xl: clamp(1.5rem, 1.25rem + 1.25vw, 2rem);
  --text-3xl: clamp(1.875rem, 1.5rem + 1.875vw, 2.5rem);
  --text-4xl: clamp(2.25rem, 1.75rem + 2.5vw, 3.5rem);
}

/* Usage */
h1 {
  font-size: var(--text-4xl);
}
h2 {
  font-size: var(--text-3xl);
}
h3 {
  font-size: var(--text-2xl);
}
p {
  font-size: var(--text-base);
}

/* Fluid spacing scale */
:root {
  --space-xs: clamp(0.25rem, 0.2rem + 0.25vw, 0.5rem);
  --space-sm: clamp(0.5rem, 0.4rem + 0.5vw, 0.75rem);
  --space-md: clamp(1rem, 0.8rem + 1vw, 1.5rem);
  --space-lg: clamp(1.5rem, 1.2rem + 1.5vw, 2.5rem);
  --space-xl: clamp(2rem, 1.5rem + 2.5vw, 4rem);
}
```

```tsx
// Utility function for fluid values
function fluidValue(
  minSize: number,
  maxSize: number,
  minWidth = 320,
  maxWidth = 1280,
) {
  const slope = (maxSize - minSize) / (maxWidth - minWidth);
  const yAxisIntersection = -minWidth * slope + minSize;

  return `clamp(${minSize}rem, ${yAxisIntersection.toFixed(4)}rem + ${(slope * 100).toFixed(4)}vw, ${maxSize}rem)`;
}

// Generate fluid type scale
const fluidTypeScale = {
  sm: fluidValue(0.875, 1),
  base: fluidValue(1, 1.125),
  lg: fluidValue(1.25, 1.5),
  xl: fluidValue(1.5, 2),
  "2xl": fluidValue(2, 3),
};
```

### Pattern 3: CSS Grid Responsive Layout

```css
/* Auto-fit grid - items wrap automatically */
.grid-auto {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(min(300px, 100%), 1fr));
  gap: 1.5rem;
}

/* Auto-fill grid - maintains empty columns */
.grid-auto-fill {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(250px, 1fr));
  gap: 1rem;
}

/* Responsive grid with named areas */
.page-layout {
  display: grid;
  grid-template-areas:
    "header"
    "main"
    "sidebar"
    "footer";
  gap: 1rem;
}

@media (min-width: 768px) {
  .page-layout {
    grid-template-columns: 1fr 300px;
    grid-template-areas:
      "header header"
      "main sidebar"
      "footer footer";
  }
}

@media (min-width: 1024px) {
  .page-layout {
    grid-template-columns: 250px 1fr 300px;
    grid-template-areas:
      "header header header"
      "nav main sidebar"
      "footer footer footer";
  }
}

.header {
  grid-area: header;
}
.main {
  grid-area: main;
}
.sidebar {
  grid-area: sidebar;
}
.footer {
  grid-area: footer;
}
```

```tsx
// Responsive grid component
function ResponsiveGrid({ children, minItemWidth = "250px", gap = "1.5rem" }) {
  return (
    <div
      className="grid"
      style={{
        gridTemplateColumns: `repeat(auto-fit, minmax(min(${minItemWidth}, 100%), 1fr))`,
        gap,
      }}
    >
      {children}
    </div>
  );
}

// Usage with Tailwind
function ProductGrid({ products }) {
  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4 md:gap-6">
      {products.map((product) => (
        <ProductCard key={product.id} product={product} />
      ))}
    </div>
  );
}
```

### Pattern 4: Responsive Navigation

```tsx
function ResponsiveNav({ items }) {
  const [isOpen, setIsOpen] = useState(false);

  return (
    <nav className="relative">
      {/* Mobile menu button */}
      <button
        className="lg:hidden p-2"
        onClick={() => setIsOpen(!isOpen)}
        aria-expanded={isOpen}
        aria-controls="nav-menu"
      >
        <span className="sr-only">Toggle navigation</span>
        {isOpen ? <X /> : <Menu />}
      </button>

      {/* Navigation links */}
      <ul
        id="nav-menu"
        className={cn(
          // Base: hidden on mobile
          "absolute top-full left-0 right-0 bg-background border-b",
          "flex flex-col",
          // Mobile: slide down
          isOpen ? "flex" : "hidden",
          // Desktop: always visible, horizontal
          "lg:static lg:flex lg:flex-row lg:border-0 lg:bg-transparent",
        )}
      >
        {items.map((item) => (
          <li key={item.href}>
            <a
              href={item.href}
              className={cn(
                "block px-4 py-3",
                "lg:px-3 lg:py-2",
                "hover:bg-muted lg:hover:bg-transparent lg:hover:text-primary",
              )}
            >
              {item.label}
            </a>
          </li>
        ))}
      </ul>
    </nav>
  );
}
```

### Pattern 5: Responsive Images

```tsx
// Responsive image with art direction
function ResponsiveHero() {
  return (
    <picture>
      {/* Art direction: different crops for different screens */}
      <source
        media="(min-width: 1024px)"
        srcSet="/hero-wide.webp"
        type="image/webp"
      />
      <source
        media="(min-width: 768px)"
        srcSet="/hero-medium.webp"
        type="image/webp"
      />
      <source srcSet="/hero-mobile.webp" type="image/webp" />

      {/* Fallback */}
      <img
        src="/hero-mobile.jpg"
        alt="Hero image description"
        className="w-full h-auto"
        loading="eager"
        fetchpriority="high"
      />
    </picture>
  );
}

// Responsive image with srcset for resolution switching
function ProductImage({ product }) {
  return (
    <img
      src={product.image}
      srcSet={`
        ${product.image}?w=400 400w,
        ${product.image}?w=800 800w,
        ${product.image}?w=1200 1200w
      `}
      sizes="(max-width: 640px) 100vw, (max-width: 1024px) 50vw, 33vw"
      alt={product.name}
      className="w-full h-auto object-cover"
      loading="lazy"
    />
  );
}
```

### Pattern 6: Responsive Tables

```tsx
// Responsive table with horizontal scroll
function ResponsiveTable({ data, columns }) {
  return (
    <div className="w-full overflow-x-auto">
      <table className="w-full min-w-[600px]">
        <thead>
          <tr>
            {columns.map((col) => (
              <th key={col.key} className="text-left p-3">
                {col.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {data.map((row, i) => (
            <tr key={i} className="border-t">
              {columns.map((col) => (
                <td key={col.key} className="p-3">
                  {row[col.key]}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// Card-based table for mobile
function ResponsiveDataTable({ data, columns }) {
  return (
    <>
      {/* Desktop table */}
      <table className="hidden md:table w-full">
        {/* ... standard table */}
      </table>

      {/* Mobile cards */}
      <div className="md:hidden space-y-4">
        {data.map((row, i) => (
          <div key={i} className="border rounded-lg p-4 space-y-2">
            {columns.map((col) => (
              <div key={col.key} className="flex justify-between">
                <span className="font-medium text-muted-foreground">
                  {col.label}
                </span>
                <span>{row[col.key]}</span>
              </div>
            ))}
          </div>
        ))}
      </div>
    </>
  );
}
```

## Viewport Units

```css
/* Standard viewport units */
.full-height {
  height: 100vh; /* May cause issues on mobile */
}

/* Dynamic viewport units (recommended for mobile) */
.full-height-dynamic {
  height: 100dvh; /* Accounts for mobile browser UI */
}

/* Small viewport (minimum) */
.min-full-height {
  min-height: 100svh;
}

/* Large viewport (maximum) */
.max-full-height {
  max-height: 100lvh;
}

/* Viewport-relative font sizing */
.hero-title {
  /* 5vw with min/max bounds */
  font-size: clamp(2rem, 5vw, 4rem);
}
```

## Best Practices

1. **Mobile-First**: Start with mobile styles, enhance for larger screens
2. **Content Breakpoints**: Set breakpoints based on content, not devices
3. **Fluid Over Fixed**: Use fluid values for typography and spacing
4. **Container Queries**: Use for component-level responsiveness
5. **Test Real Devices**: Simulators don't catch all issues
6. **Performance**: Optimize images, lazy load off-screen content
7. **Touch Targets**: Maintain 44x44px minimum on mobile
8. **Logical Properties**: Use inline/block for internationalization

## Common Issues

- **Horizontal Overflow**: Content breaking out of viewport
- **Fixed Widths**: Using px instead of relative units
- **Viewport Height**: 100vh issues on mobile browsers
- **Font Size**: Text too small on mobile
- **Touch Targets**: Buttons too small to tap accurately
- **Aspect Ratio**: Images squishing or stretching
- **Z-Index Stacking**: Overlays breaking on different screens

## Resources

- [CSS Container Queries](https://developer.mozilla.org/en-US/docs/Web/CSS/CSS_container_queries)
- [Utopia Fluid Type Calculator](https://utopia.fyi/type/calculator/)
- [Every Layout](https://every-layout.dev/)
- [Responsive Images Guide](https://web.dev/responsive-images/)
- [CSS Grid Garden](https://cssgridgarden.com/)




# Tailwind v4 + shadcn/ui Production Stack

**Production-tested**: WordPress Auditor (https://wordpress-auditor.webfonts.workers.dev)
**Last Updated**: 2026-01-20
**Versions**: tailwindcss@4.1.18, @tailwindcss/vite@4.1.18
**Status**: Production Ready ✅

---

## Quick Start (Follow This Exact Order)

```bash
# 1. Install dependencies
pnpm add tailwindcss @tailwindcss/vite
pnpm add -D @types/node tw-animate-css
pnpm dlx shadcn@latest init

# 2. Delete v3 config if exists
rm tailwind.config.ts  # v4 doesn't use this file
```

**vite.config.ts**:
```typescript
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import path from 'path'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: { alias: { '@': path.resolve(__dirname, './src') } }
})
```

**components.json** (CRITICAL):
```json
{
  "tailwind": {
    "config": "",              // ← Empty for v4
    "css": "src/index.css",
    "baseColor": "slate",
    "cssVariables": true
  }
}
```

---

## The Four-Step Architecture (MANDATORY)

Skipping steps will break your theme. Follow exactly:

### Step 1: Define CSS Variables at Root

```css
/* src/index.css */
@import "tailwindcss";
@import "tw-animate-css";  /* Required for shadcn/ui animations */

:root {
  --background: hsl(0 0% 100%);      /* ← hsl() wrapper required */
  --foreground: hsl(222.2 84% 4.9%);
  --primary: hsl(221.2 83.2% 53.3%);
  /* ... all light mode colors */
}

.dark {
  --background: hsl(222.2 84% 4.9%);
  --foreground: hsl(210 40% 98%);
  --primary: hsl(217.2 91.2% 59.8%);
  /* ... all dark mode colors */
}
```

**Critical**: Define at root level (NOT inside `@layer base`). Use `hsl()` wrapper.

### Step 2: Map Variables to Tailwind Utilities

```css
@theme inline {
  --color-background: var(--background);
  --color-foreground: var(--foreground);
  --color-primary: var(--primary);
  /* ... map ALL CSS variables */
}
```

**Why**: Generates utility classes (`bg-background`, `text-primary`). Without this, utilities won't exist.

### Step 3: Apply Base Styles

```css
@layer base {
  body {
    background-color: var(--background);  /* NO hsl() wrapper here */
    color: var(--foreground);
  }
}
```

**Critical**: Reference variables directly. Never double-wrap: `hsl(var(--background))`.

### Step 4: Result - Automatic Dark Mode

```tsx
<div className="bg-background text-foreground">
  {/* No dark: variants needed - theme switches automatically */}
</div>
```

---

## Dark Mode Setup

**1. Create ThemeProvider** (see `templates/theme-provider.tsx`)

**2. Wrap App**:
```typescript
// src/main.tsx
import { ThemeProvider } from '@/components/theme-provider'

ReactDOM.createRoot(document.getElementById('root')!).render(
  <ThemeProvider defaultTheme="dark" storageKey="vite-ui-theme">
    <App />
  </ThemeProvider>
)
```

**3. Add Theme Toggle**:
```bash
pnpm dlx shadcn@latest add dropdown-menu
```

See `reference/dark-mode.md` for ModeToggle component.

---

## Critical Rules

### ✅ Always Do:

1. Wrap colors with `hsl()` in `:root`/`.dark`: `--bg: hsl(0 0% 100%);`
2. Use `@theme inline` to map all CSS variables
3. Set `"tailwind.config": ""` in components.json
4. Delete `tailwind.config.ts` if exists
5. Use `@tailwindcss/vite` plugin (NOT PostCSS)

### ❌ Never Do:

1. Put `:root`/`.dark` inside `@layer base` (causes cascade issues)
2. Use `.dark { @theme { } }` pattern (v4 doesn't support nested @theme)
3. Double-wrap colors: `hsl(var(--background))`
4. Use `tailwind.config.ts` for theme (v4 ignores it)
5. Use `@apply` directive (deprecated in v4, see error #7)
6. Use `dark:` variants for semantic colors (auto-handled)
7. Use `@apply` with `@layer base` or `@layer components` classes (v4 breaking change - use `@utility` instead) | [Source](https://github.com/tailwindlabs/tailwindcss/discussions/17082)
8. Wrap ANY styles in `@layer base` without understanding CSS layer ordering (see error #8) | [Source](https://github.com/tailwindlabs/tailwindcss/discussions/16002)

---

## Common Errors & Solutions

This skill prevents **8 documented errors**.

### 1. ❌ tw-animate-css Import Error

**Error**: "Cannot find module 'tailwindcss-animate'"

**Cause**: shadcn/ui deprecated `tailwindcss-animate` for v4.

**Solution**:
```bash
# ✅ DO
pnpm add -D tw-animate-css

# Add to src/index.css:
@import "tailwindcss";
@import "tw-animate-css";

# ❌ DON'T
npm install tailwindcss-animate  # v3 only
```

---

### 2. ❌ Colors Not Working

**Error**: `bg-primary` doesn't apply styles

**Cause**: Missing `@theme inline` mapping

**Solution**:
```css
@theme inline {
  --color-background: var(--background);
  --color-foreground: var(--foreground);
  --color-primary: var(--primary);
  /* ... map ALL CSS variables */
}
```

---

### 3. ❌ Dark Mode Not Switching

**Error**: Theme stays light/dark

**Cause**: Missing ThemeProvider

**Solution**:
1. Create ThemeProvider (see `templates/theme-provider.tsx`)
2. Wrap app in `main.tsx`
3. Verify `.dark` class toggles on `<html>` element

---

### 4. ❌ Duplicate @layer base

**Error**: "Duplicate @layer base" in console

**Cause**: shadcn init adds `@layer base` - don't add another

**Solution**:
```css
/* ✅ Correct - single @layer base */
@import "tailwindcss";

:root { --background: hsl(0 0% 100%); }

@theme inline { --color-background: var(--background); }

@layer base { body { background-color: var(--background); } }
```

---

### 5. ❌ Build Fails with tailwind.config.ts

**Error**: "Unexpected config file"

**Cause**: v4 doesn't use `tailwind.config.ts` (v3 legacy)

**Solution**:
```bash
rm tailwind.config.ts
```

v4 configuration happens in `src/index.css` using `@theme` directive.

---

### 6. ❌ @theme inline Breaks Dark Mode in Multi-Theme Setups

**Error**: Dark mode doesn't switch when using `@theme inline` with custom variants (e.g., `data-mode="dark"`)
**Source**: [GitHub Discussion #18560](https://github.com/tailwindlabs/tailwindcss/discussions/18560)

**Cause**: `@theme inline` bakes variable VALUES into utilities at build time. When dark mode changes the underlying CSS variables, utilities don't update because they reference hardcoded values, not variables.

**Why It Happens**:
- `@theme inline` inlines VALUES at build time: `bg-primary` → `background-color: oklch(...)`
- Dark mode overrides change the CSS variables, but utilities already have baked-in values
- The CSS specificity chain breaks

**Solution**: Use `@theme` (without inline) for multi-theme scenarios:

```css
/* ✅ CORRECT - Use @theme without inline */
@custom-variant dark (&:where([data-mode=dark], [data-mode=dark] *));

@theme {
  --color-text-primary: var(--color-slate-900);
  --color-bg-primary: var(--color-white);
}

@layer theme {
  [data-mode="dark"] {
    --color-text-primary: var(--color-white);
    --color-bg-primary: var(--color-slate-900);
  }
}
```

**When to use inline**:
- Single theme + dark mode toggle (like shadcn/ui default) ✅
- Referencing other CSS variables that don't change ✅

**When NOT to use inline**:
- Multi-theme systems (data-theme="blue" | "green" | etc.) ❌
- Dynamic theme switching beyond light/dark ❌

**Maintainer Guidance** (Adam Wathan):
> "It's more idiomatic in v4 for the actual generated CSS to reference your theme variables. I would personally only use inline when things don't work without it."

---

### 7. ❌ @apply with @layer base/components (v4 Breaking Change)

**Error**: `Cannot apply unknown utility class: custom-button`
**Source**: [GitHub Discussion #17082](https://github.com/tailwindlabs/tailwindcss/discussions/17082)

**Cause**: In v3, classes defined in `@layer base` and `@layer components` could be used with `@apply`. In v4, this is a breaking architectural change.

**Why It Happens**: v4 doesn't "hijack" the native CSS `@layer` at-rule anymore. Only classes defined with `@utility` are available to `@apply`.

**Migration**:
```css
/* ❌ v3 pattern (worked) */
@layer components {
  .custom-button {
    @apply px-4 py-2 bg-blue-500;
  }
}

/* ✅ v4 pattern (required) */
@utility custom-button {
  @apply px-4 py-2 bg-blue-500;
}

/* OR use native CSS */
@layer base {
  .custom-button {
    padding: 1rem 0.5rem;
    background-color: theme(colors.blue.500);
  }
}
```

**Note**: This skill already discourages `@apply` usage. This error is primarily for users migrating from v3.

---

### 8. ❌ @layer base Styles Not Applying

**Error**: Styles defined in `@layer base` seem to be ignored
**Source**: [GitHub Discussion #16002](https://github.com/tailwindlabs/tailwindcss/discussions/16002) | [Discussion #18123](https://github.com/tailwindlabs/tailwindcss/discussions/18123)

**Cause**: v4 uses native CSS layers. Base styles CAN be overridden by utility layers due to CSS cascade if layers aren't explicitly ordered.

**Why It Happens**:
- v3: Tailwind intercepted `@layer base/components/utilities` and processed them specially
- v4: Uses native CSS layers - if you don't import layers in the right order, precedence breaks
- Styles ARE being applied, but utilities override them

**Solution Option 1**: Define layers explicitly:
```css
@import "tailwindcss/theme.css" layer(theme);
@import "tailwindcss/base.css" layer(base);
@import "tailwindcss/components.css" layer(components);
@import "tailwindcss/utilities.css" layer(utilities);

@layer base {
  body {
    background-color: var(--background);
  }
}
```

**Solution Option 2** (Recommended): Don't use `@layer base` - define styles at root level:
```css
@import "tailwindcss";

:root {
  --background: hsl(0 0% 100%);
}

body {
  background-color: var(--background); /* No @layer needed */
}
```

**Applies to**: ALL base styles, not just color variables. Avoid wrapping ANY styles in `@layer base` unless you understand CSS layer ordering.

---

## Quick Reference

| Symptom | Cause | Fix |
|---------|-------|-----|
| `bg-primary` doesn't work | Missing `@theme inline` | Add `@theme inline` block |
| Colors all black/white | Double `hsl()` wrapping | Use `var(--color)` not `hsl(var(--color))` |
| Dark mode not switching | Missing ThemeProvider | Wrap app in `<ThemeProvider>` |
| Build fails | `tailwind.config.ts` exists | Delete file |
| Animation errors | Using `tailwindcss-animate` | Install `tw-animate-css` |

---

## What's New in Tailwind v4

### OKLCH Color Space (December 2024)

Tailwind v4.0 replaced the entire default color palette with OKLCH, a perceptually uniform color space.
**Source**: [Tailwind v4.0 Release](https://tailwindcss.com/blog/tailwindcss-v4) | [OKLCH Migration Guide](https://andy-cinquin.com/blog/migration-oklch-tailwind-css-4-0)

**Why OKLCH**:
- **Perceptual consistency**: HSL's "50% lightness" is visually inconsistent across hues (yellow appears much brighter than blue at same lightness)
- **Better gradients**: Smooth transitions without muddy middle colors
- **Wider gamut**: Supports colors beyond sRGB on modern displays
- **More vibrant colors**: Eye-catching, saturated colors previously limited by sRGB

**Browser Support** (January 2026):
- Chrome 111+, Firefox 113+, Safari 15.4+, Edge 111+
- Global coverage: 93.1%

**Automatic Fallbacks**: Tailwind generates sRGB fallbacks for older browsers:
```css
.bg-blue-500 {
  background-color: #3b82f6; /* sRGB fallback */
  background-color: oklch(0.6 0.24 264); /* Modern browsers */
}
```

**Custom Colors**: When defining custom colors, OKLCH is now preferred:
```css
@theme {
  /* Modern approach (preferred) */
  --color-brand: oklch(0.7 0.15 250);

  /* Legacy approach (still works) */
  --color-brand: hsl(240 80% 60%);
}
```

**Migration**: No breaking changes - Tailwind generates fallbacks automatically. For new projects, use OKLCH-aware tooling for custom colors.

### Built-in Features (No Plugin Needed)

**Container Queries** (built-in as of v4.0):
```tsx
<div className="@container">
  <div className="@md:text-lg @lg:grid-cols-2">
    Content responds to container width, not viewport
  </div>
</div>
```

**Line Clamp** (built-in as of v3.3):
```tsx
<p className="line-clamp-3">Truncate to 3 lines with ellipsis...</p>
<p className="line-clamp-[8]">Arbitrary values supported</p>
<p className="line-clamp-(--teaser-lines)">CSS variable support</p>
```

**Removed Plugins**:
- `@tailwindcss/container-queries` - Built-in now
- `@tailwindcss/line-clamp` - Built-in since v3.3

---

## Tailwind v4 Plugins

Use `@plugin` directive (NOT `require()` or `@import`):

**Typography** (for Markdown/CMS content):
```bash
pnpm add -D @tailwindcss/typography
```
```css
@import "tailwindcss";
@plugin "@tailwindcss/typography";
```
```html
<article class="prose dark:prose-invert">{{ content }}</article>
```

**Forms** (cross-browser form styling):
```bash
pnpm add -D @tailwindcss/forms
```
```css
@import "tailwindcss";
@plugin "@tailwindcss/forms";
```

**Container Queries** (built-in, no plugin needed):
```tsx
<div className="@container">
  <div className="@md:text-lg">Responds to container width</div>
</div>
```

**Common Plugin Errors**:
```css
/* ❌ WRONG - v3 syntax */
@import "@tailwindcss/typography";

/* ✅ CORRECT - v4 syntax */
@plugin "@tailwindcss/typography";
```

---

## Setup Checklist

- [ ] `@tailwindcss/vite` installed (NOT postcss)
- [ ] `vite.config.ts` uses `tailwindcss()` plugin
- [ ] `components.json` has `"config": ""`
- [ ] NO `tailwind.config.ts` exists
- [ ] `src/index.css` follows 4-step pattern:
  - [ ] `:root`/`.dark` at root level (not in @layer)
  - [ ] Colors wrapped with `hsl()`
  - [ ] `@theme inline` maps all variables
  - [ ] `@layer base` uses unwrapped variables
- [ ] ThemeProvider wraps app
- [ ] Theme toggle works

---

## File Templates

Available in `templates/` directory:

- **index.css** - Complete CSS with all color variables
- **components.json** - shadcn/ui v4 config
- **vite.config.ts** - Vite + Tailwind plugin
- **theme-provider.tsx** - Dark mode provider
- **utils.ts** - `cn()` utility

---

## Migration from v3

See `reference/migration-guide.md` for complete guide.

**Key Changes**:
- Delete `tailwind.config.ts`
- Move theme to CSS with `@theme inline`
- Replace `@tailwindcss/line-clamp` (now built-in: `line-clamp-*`)
- Replace `tailwindcss-animate` with `tw-animate-css`
- Update plugins: `require()` → `@plugin`

### Additional Migration Gotchas

#### Automated Migration Tool May Fail

**Warning**: The `@tailwindcss/upgrade` utility often fails to migrate configurations.
**Source**: [Community Reports](https://medium.com/better-dev-nextjs-react/tailwind-v4-migration-from-javascript-config-to-css-first-in-2025-ff3f59b215ca) | [GitHub Discussion #16642](https://github.com/tailwindlabs/tailwindcss/discussions/16642)

**Common failures**:
- Typography plugin configurations
- Complex theme extensions
- Custom plugin setups

**Recommendation**: Don't rely on automated migration. Follow manual steps in the migration guide instead.

#### Default Element Styles Removed

Tailwind v4 takes a more minimal approach to Preflight, removing default styles for headings, lists, and buttons.
**Source**: [GitHub Discussion #16517](https://github.com/tailwindlabs/tailwindcss/discussions/16517) | [Medium: Migration Problems](https://medium.com/better-dev-nextjs-react/tailwind-v4-migration-from-javascript-config-to-css-first-in-2025-ff3f59b215ca)

**Impact**:
- All headings (`<h1>` through `<h6>`) render at same size
- Lists lose default padding
- Visual regressions in existing projects

**Solutions**:

**Option 1: Use @tailwindcss/typography for content pages**:
```bash
pnpm add -D @tailwindcss/typography
```
```css
@import "tailwindcss";
@plugin "@tailwindcss/typography";
```
```tsx
<article className="prose dark:prose-invert">
  {/* All elements styled automatically */}
</article>
```

**Option 2: Add custom base styles**:
```css
@layer base {
  h1 { @apply text-4xl font-bold mb-4; }
  h2 { @apply text-3xl font-bold mb-3; }
  h3 { @apply text-2xl font-bold mb-2; }
  ul { @apply list-disc pl-6 mb-4; }
  ol { @apply list-decimal pl-6 mb-4; }
}
```

#### PostCSS Setup Complexity

**Recommendation**: Use `@tailwindcss/vite` plugin for Vite projects instead of PostCSS.
**Source**: [Medium: Migration Problems](https://medium.com/better-dev-nextjs-react/tailwind-v4-migration-from-javascript-config-to-css-first-in-2025-ff3f59b215ca) | [GitHub Discussion #15764](https://github.com/tailwindlabs/tailwindcss/discussions/15764)

**Why Vite Plugin is Better**:
```typescript
// ✅ Vite Plugin - One line, no PostCSS config
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
})

// ❌ PostCSS - Multiple steps, plugin compatibility issues
// 1. Install @tailwindcss/postcss
// 2. Configure postcss.config.js
// 3. Manage plugin order
// 4. Debug plugin conflicts
```

**PostCSS Problems Reported**:
- Error: "It looks like you're trying to use tailwindcss directly as a PostCSS plugin"
- Multiple PostCSS plugins required: `postcss-import`, `postcss-advanced-variables`, `tailwindcss/nesting`
- v4 PostCSS plugin is separate package: `@tailwindcss/postcss`

**Official Guidance**: The Vite plugin is recommended for Vite projects. PostCSS is for legacy setups or non-Vite environments.

#### Visual Changes

**Ring Width Default**: Changed from 3px to 1px
**Source**: [Medium: Migration Guide](https://medium.com/better-dev-nextjs-react/tailwind-v4-migration-from-javascript-config-to-css-first-in-2025-ff3f59b215ca)

- `ring` class is now thinner
- Use `ring-3` to match v3 appearance

```tsx
// v3: 3px ring
<button className="ring">Button</button>

// v4: 1px ring (thinner)
<button className="ring">Button</button>

// Match v3 appearance
<button className="ring-3">Button</button>
```

---

## Reference Documentation

- **architecture.md** - Deep dive into 4-step pattern
- **dark-mode.md** - Complete dark mode implementation
- **common-gotchas.md** - Troubleshooting guide
- **migration-guide.md** - v3 → v4 migration

---

## Official Documentation

- **shadcn/ui Vite Setup**: https://ui.shadcn.com/docs/installation/vite
- **shadcn/ui Tailwind v4**: https://ui.shadcn.com/docs/tailwind-v4
- **Tailwind v4 Docs**: https://tailwindcss.com/docs

---

**Last Updated**: 2026-01-20
**Skill Version**: 3.0.0
**Tailwind v4**: 4.1.18 (Latest)
**Production**: WordPress Auditor (https://wordpress-auditor.webfonts.workers.dev)

**Changelog**:
- v3.0.0 (2026-01-20): Major research update - added 3 TIER 1 errors (#6-8), expanded migration guide with community findings (TIER 2), added OKLCH color space section, PostCSS complexity warnings, and migration tool limitations
- v2.0.1 (2026-01-03): Production verification
- v2.0.0: Initial release with 5 documented errors


---

---
paths: "**/*.css", "**/*.tsx", "**/*.jsx", tailwind.config.*, components.json, postcss.config.*
---

# Tailwind v4 + shadcn/ui Corrections

Claude's training may reference Tailwind v3 patterns. This project uses **Tailwind v4** with different syntax.

## Critical Differences from v3

### Configuration
- **No `tailwind.config.ts`** - v4 uses CSS-first config with `@theme` blocks
- **No PostCSS setup** - Use `@tailwindcss/vite` plugin instead
- **`components.json`** must have `"config": ""` (empty string)

### CSS Syntax
```css
/* ❌ v3 (Claude may suggest this) */
@tailwind base;
@tailwind components;
@tailwind utilities;

/* ✅ v4 (use this) */
@import "tailwindcss";
```

### Theme Configuration
```css
/* ❌ v3 - tailwind.config.ts */
theme: { colors: { primary: '#3b82f6' } }

/* ✅ v4 - in CSS file */
@theme inline {
  --color-primary: var(--primary);
  --color-background: var(--background);
}
```

### Animations Package
```bash
# ❌ v3 package (deprecated for v4)
pnpm add tailwindcss-animate

# ✅ v4 package
pnpm add -D tw-animate-css
```

```css
/* ✅ v4 import */
@import "tailwindcss";
@import "tw-animate-css";
```

### Plugins
```css
/* ❌ v3 - require() in config */
plugins: [require('@tailwindcss/typography')]

/* ✅ v4 - @plugin directive in CSS */
@plugin "@tailwindcss/typography";
```

### @apply Directive
```css
/* ❌ Deprecated in v4 */
.btn { @apply px-4 py-2 bg-primary; }

/* ✅ Use direct classes or CSS */
.btn { padding: 0.5rem 1rem; background-color: var(--primary); }
```

## Variable Architecture

CSS variables must follow this structure:

```css
/* 1. Define at root (NOT inside @layer base) */
:root {
  --background: hsl(0 0% 100%);  /* hsl() wrapper required */
  --primary: hsl(221.2 83.2% 53.3%);
}

.dark {
  --background: hsl(222.2 84% 4.9%);
  --primary: hsl(217.2 91.2% 59.8%);
}

/* 2. Map to Tailwind utilities */
@theme inline {
  --color-background: var(--background);
  --color-primary: var(--primary);
}

/* 3. Apply base styles (NO hsl wrapper here) */
@layer base {
  body {
    background-color: var(--background);
    color: var(--foreground);
  }
}
```

## Dark Mode

- No `dark:` variants needed for semantic colors - theme switches automatically
- Just use `bg-background`, `text-foreground`, etc.
- ThemeProvider toggles `.dark` class on `<html>` element

## Quick Fixes

| If Claude suggests... | Use instead... |
|----------------------|----------------|
| `@tailwind base` | `@import "tailwindcss"` |
| `tailwind.config.ts` | `@theme inline` in CSS |
| `tailwindcss-animate` | `tw-animate-css` |
| `require('@plugin')` | `@plugin "@plugin"` |
| `@apply` | Direct CSS or utility classes |
| `hsl(var(--color))` | `var(--color)` (already has hsl) |