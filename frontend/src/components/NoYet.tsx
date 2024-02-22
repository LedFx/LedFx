import { Card, CardHeader } from '@mui/material'
import { Info } from '@mui/icons-material'
import PropTypes from 'prop-types'

interface NoYetProps {
  type?: string
}

const NoYet: React.FC<NoYetProps> = ({ type }): JSX.Element => (
  <Card>
    <CardHeader
      avatar={<Info />}
      title={`No ${type}s yet`}
      subheader={`You can add your first ${type} using the plus button`}
    />
  </Card>
)

NoYet.propTypes = {
  type: PropTypes.string
}

NoYet.defaultProps = {
  type: 'Thing'
}

export default NoYet
