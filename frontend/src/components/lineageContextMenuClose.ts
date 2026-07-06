export function shouldCloseLineageContextMenu(target: EventTarget | null, menuElement: HTMLElement | null) {
  if (!menuElement) return false
  if (!target) return true
  return !menuElement.contains(target as Node)
}
