/* eslint-disable prettier/prettier */
import React from 'react'
import { styled } from '@mui/material/styles'
import PropTypes from 'prop-types'
import Button from '@mui/material/Button'
import DialogTitle from '@mui/material/DialogTitle'
import DialogContent from '@mui/material/DialogContent'
import DialogActions from '@mui/material/DialogActions'
import Dialog from '@mui/material/Dialog'
import AddCircleIcon from '@mui/icons-material/AddCircle'
import DialogContentText from '@mui/material/DialogContentText'
import InputLabel from '@mui/material/InputLabel'
import MenuItem from '@mui/material/MenuItem'
import ListSubheader from '@mui/material/ListSubheader'
import FormControl from '@mui/material/FormControl'
import Select from '@mui/material/Select'
import { Slider, Switch } from '@mui/material'
import FormHelperText from '@mui/material/FormHelperText'
import ThisDropDown from './DialogAddEventListnerDropDown'
import useStore from '../../../store/useStore'

const PREFIX = 'DialogAddEventListener'

const classes = {
  root: `${PREFIX}-root`,
  paper: `${PREFIX}-paper`,
}

const Root = styled('div')(({ theme }) => ({
  [`& .${classes.root}`]: {
    width: '100%',
    maxWidth: 360,
    backgroundColor: theme.palette.background.paper,
  },

  [`& .${classes.paper}`]: {
    width: '80%',
    maxHeight: 535,
  },
}))

function ConfirmationDialogRaw(props: any) {
  const {
    onClose,
    value: valueProp,
    open,
    ...other
  } = props
  const [valueState, setValue] = React.useState(valueProp)
  const [checkButtonType, setButtonType] = React.useState(false)
  const [checkSliderType, setSliderType] = React.useState(false)
  const [checkID, setID] = React.useState(null)
  const [dropDownRenderList, setdropDownRenderList] = React.useState([])
  const [switchValue, setSwitchValue] = React.useState(false)
  const [sliderValue, setSliderValue] = React.useState(0)
  const [formData, setformData] = React.useState({
    event_type: null,
    event_filter: {},
    qlc_payload: null,
  })
  const [qlcData, setqlcData] = React.useState([])
  const radioGroupRef = React.useRef(null)

  const qlcInfo = useStore((state: any) => state.qlc?.qlcWidgets)
  const createQlcListener = useStore((state) => state.addQLCSongTrigger)
  const getIntegrations = useStore((state) => state.getIntegrations)

  const SceneSet =
    qlcInfo &&
    qlcInfo?.event_types &&
    qlcInfo?.event_types?.scene_activated?.event_filters?.scene_id

  const EffectSet =
    qlcInfo &&
    qlcInfo?.event_types &&
    qlcInfo?.event_types.effect_set?.event_filters?.effect_name

  const temp = (qlcInfo && qlcInfo?.qlc_widgets) || []

  const QLCWidgets =
    temp.length > 0
      ? [...temp].sort(
        (a: string[], b: string[]) => parseInt(a[0], 10) - parseInt(b[0], 10)
      )
      : []

  React.useEffect(() => {
    if (!open) {
      setValue(valueProp)
    }
  }, [valueProp, open])

  const handleEntering = () => {
    if (radioGroupRef.current != null) { /* empty */ }
  }

  const handleCancel = () => {
    onClose()
  }

  const handleOk = () => {
    onClose(valueState)
    const data = JSON.stringify(formData)
    // eslint-disable-next-line no-console
    console.error('QLCFormEventTest1', data)
    createQlcListener(formData).then(() => {
      getIntegrations()
    })
  }

  const handleEventChange = (event: any) => {
    let { value } = event.target
    if (event.target.type === 'checkbox') {
      value = event.target.checked ? 255 : 0
      const qlcDatanewArr: any = qlcData.slice()
      qlcDatanewArr[0][event.target.name] = value
      const newqlcPayload = Object.assign({}, ...qlcDatanewArr)
      const newSwitchState = {
        ...formData,
        qlc_payload: {
          ...newqlcPayload,
        },
      }
      setSwitchValue(event.target.checked)
      setqlcData(qlcDatanewArr)
      setformData(newSwitchState)
    } else if (event.target.name === 'qlc_payload') {
      const qlcDatanewArr: any = qlcData.slice()
      const qlcDataObj: any = {
        [event.target.value[0]]: 0,
      }
      qlcDatanewArr[0] = qlcDataObj
      setSwitchValue(false)
      setqlcData(qlcDatanewArr)
      const newqlcPayload = Object.assign({}, ...qlcDatanewArr)

      const newSwitchState = {
        ...formData,
        qlc_payload: {
          ...newqlcPayload,
        },
      }
      setformData(newSwitchState)
    } else if (event.target.name === 'scene_id' || event.target.name === 'effect_name') {
      value = JSON.parse(value);
      const filterKey = value?.event_type === 'scene_activated' ? 'scene_id' : 'effect_name';
      const newFormState = {
        ...formData,
        event_filter: {
          [filterKey]: value?.event_name,
        },
        event_type: value?.event_type,
      };
      setformData(newFormState);
    } else {
      const qlcDatanewArr: any = qlcData.slice()
      qlcDatanewArr[0][event.target.value[0]] = value
      const newqlcPayload = Object.assign({}, ...qlcDatanewArr)
      const newSliderState = {
        ...formData,
        qlc_payload: {
          ...newqlcPayload,
        },
      }
      setSliderValue(value)
      setformData(newSliderState)
    }
  }

  const handleTypeChange = (event: any) => {
    if (event.target.value.includes('Button')) {
      setButtonType(true)
    } else {
      setButtonType(false)
    }
    if (event.target.value.includes('Slider')) {
      setSliderType(true)
    } else {
      setSliderType(false)
    }
    setSwitchValue(false)
    setID(event.target.value[0])
    handleEventChange(event)
  }

  // work here next time to eliminate reference cloning probably make different handleswitchchange
  const handleDropTypeChange = (
    event: any,
    index: any,
    val: any,
    name: any
  ) => {
    const newArr: any = dropDownRenderList.slice()
    if (
      event.target.name === 'qlc_payload' &&
      event.target.value.includes('Button')
    ) {
      newArr[index].showSwitch = true
      newArr[index].showSlider = false
    } else if (
      event.target.name === 'qlc_payload' &&
      event.target.value.includes('Slider')
    ) {
      newArr[index].showSlider = true
      newArr[index].showSwitch = false
    }

    let { value: value1 } = event.target
    if (event.target.type === 'checkbox') {
      newArr[index].switchValue = event.target.checked

      value1 = event.target.checked ? 255 : 0
      const qlcDatanewArr: any = qlcData.slice()
      qlcDatanewArr[index + 1][event.target.name] = value1
      const newqlcPayload = Object.assign({}, ...qlcDatanewArr)
      const newSwitchState = {
        ...formData,
        qlc_payload: {
          ...newqlcPayload,
        },
      }

      setqlcData(qlcDatanewArr)
      setformData(newSwitchState)
    } else if (event.target.name === 'qlc_payload') {
      const [target] = event.target.value
      newArr[index].value = target
      const qlcDatanewArr: any = qlcData.slice()
      const qlcDataObj = {
        [event.target.value[0]]: 0,
      }
      if (qlcDatanewArr[index + 1] === undefined) {
        qlcDatanewArr.push(qlcDataObj)
      } else {
        newArr[index].switchValue = false
        qlcDatanewArr[index + 1] = qlcDataObj
      }

      setqlcData(qlcDatanewArr)

      const newqlcPayload = Object.assign({}, ...qlcDatanewArr)

      const newSwitchState = {
        ...formData,
        qlc_payload: {
          ...newqlcPayload,
        },
      }
      setformData(newSwitchState)
    } else {
      const qlcDatanewArr: any = qlcData.slice()
      qlcDatanewArr[index + 1][name] = val
      const newqlcPayload = Object.assign({}, ...qlcDatanewArr)
      const newSliderState = {
        ...formData,
        qlc_payload: {
          ...newqlcPayload,
        },
      }

      setqlcData(qlcDatanewArr)
      setformData(newSliderState)
    }

    return setdropDownRenderList(newArr)
  }

  const handleTypeAddDropDown = () => {
    const newItem: any = {
      id: Date.now(),
      value: '',
      switchValue: false,
      showSwitch: false,
      showSlider: false,
    }

    const newArr: any = dropDownRenderList.slice()
    newArr.push(newItem)
    return setdropDownRenderList(newArr)
  }

  const handleTypeRemoveDropDown = (idx: any) => {
    const newArr = dropDownRenderList.slice()
    newArr.splice(idx, 1)
    const newQlcData = qlcData.slice()
    newQlcData.splice(idx + 1, 1)
    setqlcData(newQlcData)
    const newqlcPayload = Object.assign({}, ...newQlcData)
    const newSwitchState = {
      ...formData,
      qlc_payload: {
        ...newqlcPayload,
      },
    }
    setformData(newSwitchState)
    return setdropDownRenderList(newArr)
  }

  const marks = [
    { value: 1, label: '1' },
    { value: 255, label: '255' },
  ]

  delete other.deviceList

  return (
    <Dialog
      disableBackdropClick
      disableEscapeKeyDown
      maxWidth="xs"
      onEntering={handleEntering}
      aria-labelledby="confirmation-dialog-title"
      open={open}
      {...other}
    >
      <DialogTitle id="confirmation-dialog-title">
        Event Listener Setup: {valueProp?.id}
      </DialogTitle>
      <DialogContent dividers>
        <DialogContentText>
          Trigger <b>Actions</b> based on <b>Events</b>.
        </DialogContentText>
        <FormControl className={classes.root} style={{ margin: '1rem 0'}}>
          <InputLabel htmlFor="grouped-select">
            Event
          </InputLabel>
          <Select
            variant='outlined'
            id="grouped-select"
            placeholder='If THIS'
            name={formData?.event_type === 'effect_set' ? 'effect_name' : 'scene_id'}
            onChange={handleEventChange}
            sx={{ minWidth: 250 }}
          >
            <MenuItem value="">
              <em>None</em>
            </MenuItem>
            <ListSubheader color="primary">Scene Set</ListSubheader>
            {SceneSet &&
              SceneSet.length > 0 &&
              SceneSet.map((val: any, idx: any) => (
                <MenuItem
                  key={idx}
                  value={JSON.stringify({
                    event_type: 'scene_activated',
                    event_name: val,
                  })}
                >
                  <option>{val}</option>
                </MenuItem>
              ))}
            <ListSubheader color="primary">Effect Set</ListSubheader>

            {EffectSet && EffectSet.map((effect_name: string, idx: number) => (
              <MenuItem
                key={idx}
                value={JSON.stringify({
                  event_type: 'effect_set',
                  event_name: effect_name,
                })}
              >
                <option>{effect_name}</option>
              </MenuItem>
            ))}
          </Select>
        </FormControl>
        <FormHelperText>
          {/* {' '}
          If you select an existing event trigger, then this will update/replace
          the existing `Then Do This`. */}
        </FormHelperText>
        <FormControl className={classes.root}>
          <InputLabel htmlFor="grouped-select">Action</InputLabel>
          <Select
            labelId="demo-simple-select-helper-label"
            id="demo-simple-select-helper"
            placeholder='Then Do THIS'
            variant='outlined'
            // value={formData.qlc_payload}
            name="qlc_payload"
            onChange={handleTypeChange}
            sx={{ minWidth: 250 }}
          >
            <MenuItem value="" />
            {QLCWidgets &&
              QLCWidgets.length > 0 &&
              QLCWidgets.map((e: any, f: any) => (
                <MenuItem
                  key={f}
                  value={e}
                  //  name={e[0]}
                >
                  <option>
                    ID: {e[0]}, Type: {e[1]}, Name: {e[2]}
                  </option>
                </MenuItem>
              ))}
          </Select>
        </FormControl>
        <Root>
          {checkButtonType && (
            <label>QLC+ widget selected above (On/Off) </label>
          )}
          {checkButtonType && (
            <Switch
              color="primary"
              checked={switchValue}
              name={checkID || ''}
              onChange={handleEventChange}
            />
          )}
        </Root>

        <div style={{ minWidth: '150px' }}>
          {checkSliderType && <label>QLC Slider Widget Value</label>}
          {checkSliderType && (
            <Slider
              aria-labelledby="discrete-slider"
              valueLabelDisplay="auto"
              marks={marks}
              step={1}
              min={0}
              max={255}
              defaultValue={1}
              value={sliderValue}
              onChange={handleEventChange}
            />
          )}
        </div>
        {dropDownRenderList.map((item: any, idx) => (
          <ThisDropDown
            idx={idx}
            QLCWidgets={QLCWidgets}
            value={item?.value}
            switchValue={item?.switchValue}
            showSwitch={item?.showSwitch}
            showSlider={item?.showSlider}
            handleDropTypeChange={handleDropTypeChange}
            handleTypeRemoveDropDown={handleTypeRemoveDropDown}
          />
        ))}
        {/* If Below button pressed, then show additional 'Then do this' dropdown field. */}
        <Button
          sx={{ mt: 2, mb: 3}}
          fullWidth
          color="primary"
          aria-label="Add"
          endIcon={<AddCircleIcon />}
          onClick={handleTypeAddDropDown}
          role="listitem"
        >
          ADD Action
        </Button>
      </DialogContent>
      <DialogActions>
        <Button autoFocus onClick={handleCancel} color="primary">
          Cancel
        </Button>
        <Button onClick={handleOk} color="primary" sx={{ mr: 2}}>
          Ok
        </Button>
      </DialogActions>
    </Dialog>
  )
}

ConfirmationDialogRaw.propTypes = {
  onClose: PropTypes.func.isRequired,
  open: PropTypes.bool.isRequired,
  value: PropTypes.string.isRequired,
}

export default function ConfirmationDialog({ integration }: any) {
  const [open, setOpen] = React.useState(false)

  const handleClickListItem = () => {
    setOpen(true)
  }

  const handleClose = () => {
    setOpen(false)
  }

  return (
    <div className={classes.root}>
      <Button
        variant="contained"
        color="primary"
        aria-label="Add"
        endIcon={<AddCircleIcon />}
        onClick={handleClickListItem}
        role="listitem"
      >
        ADD EVENT LISTENER
      </Button>

      <ConfirmationDialogRaw
        open={open}
        onClose={handleClose}
        value={integration}
      />
    </div>
  )
}
