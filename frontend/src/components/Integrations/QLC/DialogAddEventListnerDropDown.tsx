import React from 'react'
import InputLabel from '@mui/material/InputLabel'
import MenuItem from '@mui/material/MenuItem'
import FormControl from '@mui/material/FormControl'
import Select from '@mui/material/Select'
import DeleteIcon from '@mui/icons-material/Delete'
import { InputAdornment, Slider, Switch } from '@mui/material'

const marks = [
  { value: 1, label: '1' },
  { value: 255, label: '255' }
]
interface DropDownProps {
  // key: any;
  idx: number
  QLCWidgets: Array<[]>
  // id: any;
  value: any
  switchValue: any
  showSwitch: any
  showSlider: boolean
  handleDropTypeChange: any
  handleTypeRemoveDropDown: any
}

const ThisDropDown: React.FC<DropDownProps> = (props) => {
  const {
    // key,
    idx,
    QLCWidgets,
    // id,
    value,
    switchValue,
    showSwitch,
    showSlider,
    handleDropTypeChange,
    handleTypeRemoveDropDown
  } = props
  return (
    <>
      <FormControl fullWidth sx={{ mt: 2 }}>
        <InputLabel htmlFor="grouped-select">Action</InputLabel>
        <Select
          fullWidth
          endAdornment={
            <InputAdornment
              position="end"
              sx={{ mr: 2, cursor: 'pointer' }}
              onClick={(e) => {
                e.preventDefault()
                handleTypeRemoveDropDown(idx)
              }}
            >
              <DeleteIcon />
            </InputAdornment>
          }
          variant="outlined"
          labelId="demo-simple-select-helper-label"
          id="demo-simple-select-helper"
          name="qlc_payload"
          // value={value}
          onChange={(event) => handleDropTypeChange(event, idx)}
        >
          {QLCWidgets &&
            QLCWidgets.length > 0 &&
            QLCWidgets.map((e: any, f: any) => (
              <MenuItem key={f} value={e}>
                ID: {e[0]}, Type: {e[1]}, Name: {e[2]}
              </MenuItem>
            ))}
        </Select>
      </FormControl>
      <div style={{ minWidth: '150px' }} />
      {showSwitch && <label>QLC+ widget selected above (On/Off) </label>}
      {showSwitch && (
        <Switch
          color="primary"
          name={value}
          checked={switchValue}
          onChange={(event) => handleDropTypeChange(event, idx)}
        />
      )}
      <div style={{ minWidth: '150px' }}>
        {showSlider && <label>QLC Slider Widget Value</label>}
        {showSlider && (
          <Slider
            aria-labelledby="discrete-slider"
            valueLabelDisplay="auto"
            marks={marks}
            step={1}
            min={0}
            max={255}
            defaultValue={1}
            onChange={(event, val) =>
              handleDropTypeChange(event, idx, val, val)
            }
          />
        )}
      </div>
    </>
  )
}
export default ThisDropDown
