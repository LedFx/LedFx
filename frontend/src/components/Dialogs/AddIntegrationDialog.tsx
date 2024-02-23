/* eslint-disable @typescript-eslint/indent */
/* eslint-disable no-unused-expressions */
/* eslint-disable no-restricted-syntax */
/* eslint-disable guard-for-in */
import { useState, useEffect } from 'react'
import { styled } from '@mui/material/styles'
import {
  Button,
  MenuItem,
  Select,
  DialogTitle,
  DialogContentText,
  DialogContent,
  DialogActions,
  Dialog,
  Divider
} from '@mui/material'
import useStore from '../../store/useStore'
import BladeSchemaForm from '../SchemaForm/SchemaForm/SchemaForm'

const PREFIX = 'AddIntegrationDialog'

const classes = {
  wrapper: `${PREFIX}-wrapper`
}

const StyledDialog = styled(Dialog)(({ theme }) => ({
  [`& .${classes.wrapper}`]: {
    minWidth: '200px',
    padding: '16px 1.2rem 6px 1.2rem',
    border: '1px solid #999',
    borderRadius: '10px',
    position: 'relative',
    margin: '1rem 0',
    display: 'flex',
    alignItems: 'center',
    '@media (max-width: 580px)': {
      width: '100%',
      margin: '0.5rem 0'
    },
    '& > label': {
      top: '-0.7rem',
      display: 'flex',
      alignItems: 'center',
      left: '1rem',
      padding: '0 0.3rem',
      position: 'absolute',
      fontVariant: 'all-small-caps',
      fontSize: '0.9rem',
      letterSpacing: '0.1rem',
      backgroundColor: theme.palette.background.paper,
      boxSizing: 'border-box'
    }
  }
}))

const AddIntegrationDialog = () => {
  const getIntegrations = useStore((state) => state.getIntegrations)

  const addIntegration = useStore((state) => state.addIntegration)
  const updateIntegration = useStore((state) => state.updateIntegration)
  const integrations = useStore((state) => state.integrations)
  const features = useStore((state) => state.features) as any

  const open = useStore((state) => state.dialogs.addIntegration?.open || false)

  const integrationId = useStore(
    (state) => state.dialogs.addIntegration?.edit || false
  )
  const initial =
    typeof integrationId === 'string'
      ? integrations[integrationId]
      : { type: '', config: {} }

  const setDialogOpenAddIntegration = useStore(
    (state) => state.setDialogOpenAddIntegration
  )

  const integrationsTypes = useStore((state) => state.schemas?.integrations)
  const showSnackbar = useStore((state) => state.ui.showSnackbar)
  const [integrationType, setIntegrationType] = useState('')
  const [model, setModel] = useState({})

  const currentSchema = integrationType
    ? integrationsTypes[integrationType].schema
    : {}

  const handleClose = () => {
    setDialogOpenAddIntegration(false)
  }
  const handleAddDevice = () => {
    const cleanedModel = Object.fromEntries(
      Object.entries(model).filter(([_, v]) => v !== '')
    )
    const defaultModel = {} as any

    for (const key in currentSchema.properties) {
      currentSchema.properties[key].default !== undefined
        ? (defaultModel[key] = currentSchema.properties[key].default)
        : undefined
    }

    const valid = !currentSchema.required
      ? true
      : currentSchema.required?.every((val: string) =>
          Object.keys({ ...defaultModel, ...cleanedModel }).includes(val)
        )

    if (!valid) {
      showSnackbar('warning', 'Please fill in all required fields.')
    } else if (
      initial.config &&
      Object.keys(initial.config).length === 0 &&
      initial.config?.constructor === Object
    ) {
      // console.log("ADDING");
      addIntegration({
        type: integrationType,
        config: { ...defaultModel, ...cleanedModel }
      }).then((res) => {
        if (res !== 'failed') {
          setDialogOpenAddIntegration(false)
          getIntegrations()
        }
      })
    } else {
      // console.log("EDITING");
      updateIntegration({
        id: integrationId,
        type: integrationType,
        config: { ...model }
      }).then((res) => {
        if (res !== 'failed') {
          setDialogOpenAddIntegration(false)
          getIntegrations()
        }
      })
    }
  }
  const handleTypeChange = (value: string, init = {}) => {
    setIntegrationType(value)
    setModel(init)
  }
  const handleModelChange = (config: any) => {
    setModel({ ...model, ...config })
  }

  useEffect(() => {
    handleTypeChange(initial.type, initial.config)
  }, [initial.type])

  return (
    <StyledDialog
      open={open}
      onClose={handleClose}
      aria-labelledby="form-dialog-title"
    >
      <DialogTitle id="form-dialog-title">
        {initial.config &&
        Object.keys(initial.config).length === 0 &&
        initial.config?.constructor === Object
          ? 'Add'
          : 'Edit'}{' '}
        {integrationType.toUpperCase()} Integration
      </DialogTitle>
      <DialogContent>
        {!integrationType && (
          <DialogContentText>
            To add an interation to LedFx, please first select the type of
            integration you wish to add then provide the necessary
            configuration.
          </DialogContentText>
        )}
        <div className={classes.wrapper}>
          <label>Integration Type</label>
          <Select
            label="Type"
            style={{ flexGrow: 1 }}
            value={integrationType}
            onChange={(e: any) => handleTypeChange(e.target.value)}
          >
            {integrationsTypes &&
              Object.keys(integrationsTypes).map((item, i) => (
                <MenuItem
                  key={i}
                  value={item}
                  disabled={integrationsTypes[item].beta && !features[item]}
                >
                  {integrationsTypes[item].name}
                </MenuItem>
              ))}
          </Select>
        </div>
        <Divider style={{ marginBottom: '1rem' }} />
        {model && (
          <BladeSchemaForm
            hideToggle={!integrationType}
            type={integrationType}
            schema={currentSchema}
            model={model}
            onModelChange={handleModelChange}
          />
        )}
      </DialogContent>
      <DialogActions>
        <Button onClick={handleClose} color="primary">
          Cancel
        </Button>
        <Button onClick={handleAddDevice} color="primary">
          {initial.config &&
          Object.keys(initial.config).length === 0 &&
          initial.config?.constructor === Object
            ? 'Add'
            : 'Save'}
        </Button>
      </DialogActions>
    </StyledDialog>
  )
}

export default AddIntegrationDialog
