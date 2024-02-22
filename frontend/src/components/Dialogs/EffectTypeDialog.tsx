import {
  Autocomplete,
  Dialog,
  DialogContent,
  TextField,
  ToggleButton,
  ToggleButtonGroup,
  Typography
  // useTheme
} from '@mui/material'
import { useMemo, useState } from 'react'
import { ArrowDropDown, Search } from '@mui/icons-material'
import useStore from '../../store/useStore'
import { EffectDropDownProps } from '../SchemaForm/components/DropDown/DropDown.props'
import useStyles from '../SchemaForm/components/DropDown/DropDown.styles'
import BladeFrame from '../SchemaForm/components/BladeFrame'

const EffectTypeDialog = ({
  value,
  onChange,
  groups,
  showFilter,
  title
}: EffectDropDownProps) => {
  const dialogOpen = useStore(
    (state) => state.dialogs.effectType?.open || false
  )
  const setDialogOpen = useStore((state) => state.setDialogOpenEffectType)
  const handleClose = () => {
    setDialogOpen(false)
  }

  const classes = useStyles()
  // const theme = useTheme()
  const [formats, setFormats] = useState(
    () => groups && Object.keys(groups).map((c) => c || [])
  )
  const handleFormat = (_: any, newFormats: any) => {
    setFormats(newFormats)
  }
  //   const handleFormatb = (e: any) => {
  //     setFormats(e.target.value)
  //   }
  const yopt = useMemo(
    () => [
      ...Object.keys(groups || {})
        .flatMap(
          (c) =>
            formats &&
            formats.indexOf(c) !== -1 &&
            groups[c].flatMap((e: any) => [
              { value: e.id, label: e.name, group: c }
            ])
        )
        .filter((e: any) => !!e?.value)
    ],
    [groups, formats]
  )
  const yoptAll = useMemo(
    () => [
      ...Object.keys(groups || {})
        .flatMap((c) =>
          groups[c].flatMap((e: any) => [
            { value: e.id, label: e.name, group: c }
          ])
        )
        .filter((e: any) => !!e?.value)
    ],
    [groups, formats]
  )

  return (
    <div key="effectTypeSelector">
      <BladeFrame
        title={title}
        onClick={() => setDialogOpen(true)}
        style={{
          cursor: 'pointer',
          marginBottom: 0,
          display: 'flex',
          flexDirection: 'row',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: 0
        }}
      >
        <Typography
          variant="body1"
          sx={{
            flexGrow: 1,
            padding: '16px 1.2rem 14px 1.2rem',
            borderRadius: '10px',
            border: '1px solid #666666',
            '&:hover': {
              border: '1px solid #f9f9fb'
            }
          }}
        >
          {yoptAll.find((o) => o.value === value)?.label || ''}
          <ArrowDropDown
            sx={{
              position: 'absolute',
              right: 10,
              top: 16,
              paddingBottom: 1,
              fontSize: 30,
              zIndex: 0
            }}
          />
        </Typography>
      </BladeFrame>
      <Dialog
        open={dialogOpen}
        onClose={handleClose}
        aria-labelledby="form-dialog-title"
        sx={{
          '& .MuiDialog-paper': {
            overflowY: 'hidden'
          }
        }}
      >
        <DialogContent
          sx={{
            height: '80vh',
            maxHeight: '200vh',
            overflow: 'hidden',
            padding: '5px !important',

            '& .MuiAutocomplete-listbox': {
              maxHeight: `calc(80vh - ${showFilter ? 112 : 66}px) !important`,
              paddingTop: '0px !important'
            },
            '& .MuiAutocomplete-groupLabel': {
              backgroundColor: '#3f3f41 !important'
            }
          }}
        >
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
          <Autocomplete
            autoFocus
            popupIcon={<Search />}
            open
            fullWidth
            disablePortal
            value={value}
            onChange={(e: any, b: any) => {
              const ne = { ...e, target: { ...e.target, value: b.value } }
              if (onChange) {
                setDialogOpen(false)
                onChange(ne)
              }
              return null
            }}
            sx={{
              pb: '0px',
              width: '100%',
              minWidth: '300px',
              height: '100%',
              maxHeight: '100%',
              '& .MuiAutocomplete-popupIndicator': {
                transform: 'none',
                right: 5
              },
              '& .MuiAutocomplete-paper': {
                height: '100%',
                maxHeight: '100%'
              }
            }}
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
                // label={title}
                variant="outlined"
                fullWidth
              />
            )}
          />
        </DialogContent>
      </Dialog>
    </div>
  )
}
export default EffectTypeDialog
