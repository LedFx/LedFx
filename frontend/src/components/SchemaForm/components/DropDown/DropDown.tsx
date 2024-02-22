// import {
//   Autocomplete,
//   Checkbox,
//   ListItemText,
//   MenuItem,
//   Select,
//   TextField,
//   ToggleButton,
//   ToggleButtonGroup
// } from '@mui/material'
// import { useMemo, useState } from 'react'
import {
  EffectDropDownDefaultProps,
  EffectDropDownProps
} from './DropDown.props'
// import useStyles from './DropDown.styles'
import EffectTypeDialog from '../../../Dialogs/EffectTypeDialog'

const EffectDropDown = ({
  value,
  onChange,
  groups,
  showFilter,
  title
}: EffectDropDownProps) => {
  // const classes = useStyles()
  // const [formats, setFormats] = useState(
  //   () => groups && Object.keys(groups).map((c) => c || [])
  // )
  // const handleFormat = (_: any, newFormats: any) => {
  //   setFormats(newFormats)
  // }
  // const handleFormatb = (e: any) => {
  //   setFormats(e.target.value)
  // }
  // const yopt = useMemo(
  //   () => [
  //     ...Object.keys(groups || {})
  //       .flatMap(
  //         (c) =>
  //           formats &&
  //           formats.indexOf(c) !== -1 &&
  //           groups[c].flatMap((e: any) => [
  //             { value: e.id, label: e.name, group: c }
  //           ])
  //       )
  //       .filter((e: any) => !!e?.value)
  //   ],
  //   [groups, formats]
  // )

  return (
    <>
      {/* <Autocomplete
        fullWidth
        blurOnSelect
        value={value}
        onChange={(e: any, b: any) => {
          const ne = { ...e, target: { ...e.target, value: b.value } }
          if (onChange) return onChange(ne)
          return null
        }}
        sx={{ pb: '0px', pt: '5px !important', width: '100%' }}
        groupBy={(option) => option.group}
        options={yopt}
        isOptionEqualToValue={(option, nvalue) => option.value === nvalue}
        disableClearable
        getOptionLabel={(option) => {
          if (typeof option !== 'string') return option.label
          return yopt.find((o) => o.value === option)?.label || ''
        }}
        renderInput={(params) => (
          <TextField
            {...params}
            value={yopt.find((o) => o.value === value)?.label || ''}
            label={title}
            variant="outlined"
            fullWidth
          />
        )}
      />
      {showFilter && (
        <ToggleButtonGroup
          value={formats}
          onChange={handleFormat}
          aria-label="text formatting"
          className={classes.FormToggleWrapper}
        >
          {groups &&
            Object.keys(groups).map((c, i) => (
              <ToggleButton
                className={classes.FormToggle}
                key={i}
                value={c}
                aria-label={c}
              >
                {c}
              </ToggleButton>
            ))}
        </ToggleButtonGroup>
      )}
      {showFilter && (
        <Select
          fullWidth
          value={formats}
          onChange={handleFormatb}
          multiple
          sx={{ pb: '5px', pt: '0 !important', width: '100%' }}
          variant="outlined"
          renderValue={(selected) => selected.join(', ')}
        >
          {groups &&
            Object.keys(groups).map((c, i) => (
              <MenuItem key={i} value={c}>
                <Checkbox checked={formats.indexOf(c) > -1} />
                <ListItemText primary={c} />
              </MenuItem>
            ))}
        </Select>
      )} */}
      <EffectTypeDialog
        title={title}
        value={value}
        onChange={onChange}
        groups={groups}
        showFilter={showFilter}
      />
    </>
  )
}
EffectDropDown.defaultProps = EffectDropDownDefaultProps

export default EffectDropDown
