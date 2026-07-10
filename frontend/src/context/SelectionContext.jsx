import { createContext, useContext, useMemo, useState } from 'react'

const SelectionContext = createContext(null)

export function SelectionProvider({ children }) {
  const [selectedFilePath, setSelectedFilePath] = useState(null)

  const value = useMemo(
    () => ({ selectedFilePath, setSelectedFilePath }),
    [selectedFilePath],
  )

  return (
    <SelectionContext.Provider value={value}>{children}</SelectionContext.Provider>
  )
}

// eslint-disable-next-line react-refresh/only-export-components -- hook colocated with provider
export function useSelection() {
  const ctx = useContext(SelectionContext)
  if (!ctx) {
    throw new Error('useSelection must be used within SelectionProvider')
  }
  return ctx
}
