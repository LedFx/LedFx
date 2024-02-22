import { Box } from '@mui/material'
import type { ReactNode } from 'react'

export interface TabPanelProps {
  // eslint-disable-next-line react/require-default-props
  children?: ReactNode
  index: number
  value: number
  minHeight: number
}

export function CustomTabPanel(props: TabPanelProps) {
  const { children, value, index, minHeight, ...other } = props

  return (
    <div
      role="tabpanel"
      hidden={value !== index}
      id={`simple-tabpanel-${index}`}
      aria-labelledby={`simple-tab-${index}`}
      {...other}
    >
      {value === index && <Box sx={{ pt: 2, minHeight }}>{children}</Box>}
    </div>
  )
}

export function a11yProps(index: number) {
  return {
    id: `simple-tab-${index}`,
    'aria-controls': `simple-tabpanel-${index}`
  }
}
