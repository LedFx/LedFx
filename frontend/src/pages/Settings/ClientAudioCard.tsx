import { MenuItem, Select } from '@mui/material'
import { styled } from '@mui/material/styles'
import BladeFrame from '../../components/SchemaForm/components/BladeFrame'
import useStore from '../../store/useStore'

const PREFIX = 'ClientAudioCard'

const classes = {
  select: `${PREFIX}-select`
}

const StyledBladeFrame = styled(BladeFrame)(() => ({
  [`&.${classes.select}`]: {
    '& div.MuiSelect-select': {
      padding: '6px 0'
    }
  }
}))

const ClientAudioCard = ({ style }: any) => {
  const clientDevice = useStore((state) => state.clientDevice)
  const clientDevices = useStore((state) => state.clientDevices)
  const setClientDevice = useStore((state) => state.setClientDevice)
  const webAudName = useStore((state) => state.webAudName)

  return (
    clientDevices && (
      <StyledBladeFrame
        style={{ order: 0, ...style }}
        full
        title={`${webAudName}: Audio Device`}
        className={classes.select}
      >
        <Select
          value={clientDevice || clientDevices[0].deviceId}
          style={{ width: '100%' }}
          onChange={(e) => {
            setClientDevice(e.target.value)
          }}
        >
          {clientDevices
            .filter((cd: any) => cd.kind === 'audioinput')
            .map((d: any, i: number) => (
              <MenuItem key={i} value={d.deviceId}>
                {d.label}
              </MenuItem>
            ))}
        </Select>
      </StyledBladeFrame>
    )
  )
}

export default ClientAudioCard
