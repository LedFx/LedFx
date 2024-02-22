import { Switch, Typography } from '@mui/material'
import BladeFrame from '../../../../components/SchemaForm/components/BladeFrame'

const MSwitch = ({ group, setGroup }: any) => {
  return (
    <BladeFrame
      title="Group"
      style={{
        justifyContent: 'space-between',
        paddingRight: 2,
        marginBottom: '1rem'
      }}
    >
      <Typography>Assign multiple</Typography>
      <Switch checked={group} onClick={() => setGroup(!group)} />
    </BladeFrame>
  )
}

export default MSwitch
