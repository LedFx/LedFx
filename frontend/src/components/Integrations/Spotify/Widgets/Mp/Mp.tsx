import { Box } from '@mui/material'

import useStyle from './Mp.styles'
import MpFloating from './MpFloating'

const Mp = () => {
  const classes = useStyle()

  return (
    <Box component={MpFloating}>
      <div className={classes.Widget}>
        <Box
          bgcolor="#111"
          height={50}
          alignItems="center"
          justifyContent="center"
          display="flex"
        >
          Player
        </Box>
        {/* <iframe
          title="multitrack"
          src="/mp/index.html"
          style={{
            width: '960px',
            border: 0,
            height: 620,
            overflowY: 'auto'
          }}
        /> */}
      </div>
    </Box>
  )
}

Mp.defaultProps = {
  drag: false
}
export default Mp
