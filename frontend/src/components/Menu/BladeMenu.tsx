import React from 'react'
import Menu from '@mui/material/Menu'

const BladeMenu = React.forwardRef((props, ref) => {
  return <Menu ref={ref as any} open={false} {...props} />
})

export default BladeMenu
