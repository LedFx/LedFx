import React from 'react'
import MenuItem from '@mui/material/Menu'

const BladeMenuItem = React.forwardRef((props, ref) => {
  return <MenuItem ref={ref as any} open={false} {...props} />
})

export default BladeMenuItem
