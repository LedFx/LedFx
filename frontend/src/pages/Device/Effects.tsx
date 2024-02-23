/* eslint-disable @typescript-eslint/indent */
/* eslint-disable consistent-return */
/* eslint-disable no-restricted-syntax */
import { useEffect, useState } from 'react'
import {
  Button,
  Card,
  CardContent,
  Accordion,
  AccordionDetails,
  AccordionSummary,
  Typography,
  Box
} from '@mui/material'
import {
  Clear,
  ExpandMore,
  Pause,
  PlayArrow,
  GridOn,
  GridOff
} from '@mui/icons-material'
import useStore from '../../store/useStore'
import EffectDropDown from '../../components/SchemaForm/components/DropDown/DropDown.wrapper'
import BladeEffectSchemaForm from '../../components/SchemaForm/EffectsSchemaForm/EffectSchemaForm'
import PixelGraph from '../../components/PixelGraph'
import TourEffect from '../../components/Tours/TourEffect'
import TroubleshootButton from './TroubleshootButton'
import { Schema } from '../../components/SchemaForm/SchemaForm/SchemaForm.props'
import { EffectConfig, Virtual } from '../../store/api/storeVirtuals'

const configOrder = ['color', 'number', 'integer', 'string', 'boolean']

const orderEffectProperties = (
  schema: Schema,
  hidden_keys?: string[],
  advanced_keys?: string[],
  advanced?: boolean
) => {
  const properties: any[] =
    schema &&
    schema.properties &&
    Object.keys(schema.properties)
      .filter((k) => {
        if (hidden_keys && hidden_keys.length > 0) {
          return hidden_keys?.indexOf(k) === -1
        }
        return true
      })
      .filter((ke) => {
        if (advanced_keys && advanced_keys.length > 0 && !advanced) {
          return advanced_keys?.indexOf(ke) === -1
        }
        return true
      })
      .map((sk) => ({
        ...schema.properties[sk],
        id: sk
      }))
  const ordered = [] as any[]
  configOrder.forEach((type) => {
    ordered.push(...properties.filter((x) => x.type === type))
  })
  ordered.push(...properties.filter((x) => !configOrder.includes(x.type)))
  return ordered
    .sort((a) => (a.id === 'advanced' ? 1 : -1))
    .sort((a) => (a.type === 'string' && a.enum && a.enum.length ? -1 : 1))
    .sort((a) => (a.type === 'number' ? -1 : 1))
    .sort((a) => (a.type === 'integer' ? -1 : 1))
    .sort((a) => (a.id === 'bg_color' ? -1 : 1))
    .sort((a) => (a.type === 'color' ? -1 : 1))
    .sort((a) => (a.id === 'color' ? -1 : 1))
    .sort((a) => (a.id === 'gradient' ? -1 : 1))
}

const EffectsCard = ({ virtId }: { virtId: string }) => {
  const [fade, setFade] = useState(false)
  const [matrix, setMatrix] = useState(false)
  const getVirtuals = useStore((state) => state.getVirtuals)
  const getSchemas = useStore((state) => state.getSchemas)
  const clearEffect = useStore((state) => state.clearEffect)
  const setEffect = useStore((state) => state.setEffect)
  const updateEffect = useStore((state) => state.updateEffect)
  const virtuals = useStore((state) => state.virtuals)
  const effects = useStore((state) => state.schemas.effects)
  const setPixelGraphs = useStore((state) => state.setPixelGraphs)
  const viewMode = useStore((state) => state.viewMode)
  const effectDescriptions = useStore((state) => state.ui.effectDescriptions)
  const updateVirtual = useStore((state) => state.updateVirtual)
  const features = useStore((state) => state.features)
  const [virtual, setVirtual] = useState<Virtual | undefined>(undefined)

  const graphs = useStore((state) => state.graphs)
  const getV = () => {
    for (const prop in virtuals) {
      if (virtuals[prop].id === virtId) {
        return virtuals[prop]
      }
    }
  }

  useEffect(() => {
    const v = getV()
    if (v) setVirtual(v)
  }, [JSON.stringify(virtuals[virtId])])

  const effectType = virtual && virtual.effect.type
  const [theModel, setTheModel] = useState(virtual?.effect?.config)
  const orderedProperties =
    effects &&
    effectType &&
    orderEffectProperties(
      effects[effectType].schema,
      effects[effectType].hidden_keys,
      effects[effectType].advanced_keys,
      theModel?.advanced
    )
  const handleClearEffect = () => {
    if (virtual) {
      clearEffect(virtId).then(() => {
        setFade(true)
        setTimeout(() => {
          getVirtuals()
        }, virtual.config.transition_time * 1000)
        setTimeout(
          () => {
            setFade(false)
          },
          virtual.config.transition_time * 1000 + 300
        )
      })
    }
  }

  const handleEffectConfig = (config: EffectConfig) => {
    if (updateEffect && getVirtuals !== undefined && effectType) {
      updateEffect(virtId, effectType, config, false).then(() => {
        getVirtuals()
      })
    }
  }

  const handlePlayPause = () => {
    if (virtual)
      updateVirtual(virtual.id, !virtual.active).then(() => getVirtuals())
  }

  useEffect(() => {
    getVirtuals()
    getSchemas()
    if (graphs) {
      setPixelGraphs([virtId])
    }
  }, [graphs, setPixelGraphs, getVirtuals, getSchemas, effectType])

  useEffect(() => {
    // if (virtuals && virtual?.effect?.config) {
    //   setTheModel(virtual.effect.config)
    // } else

    if (
      virtuals &&
      virtuals[virtId]?.effect?.config &&
      JSON.stringify(theModel) !==
        JSON.stringify(virtuals[virtId].effect.config)
    ) {
      // console.log('virtuals[virtId]', virtuals[virtId].effect?.config)

      setTheModel(virtual?.effect.config)
    }
  }, [
    virtuals,
    virtuals[virtId],
    virtuals[virtId]?.effect,
    JSON.stringify(virtuals[virtId]?.effect?.config),
    virtual,
    virtual?.effect,
    virtual?.effect.config,
    effectType
  ])

  // console.log('virtual', virtual?.effect?.config)
  return (
    <>
      <Card
        variant="outlined"
        sx={{
          '& > .MuiCardContent-root': {
            pb: '0.25rem'
          }
        }}
      >
        <CardContent>
          <div
            style={{
              display: 'flex',
              flexDirection: 'column-reverse',
              justifyContent: 'space-between'
            }}
          >
            <h1>{virtual && virtual.config.name}</h1>
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'flex-end'
              }}
            >
              {effects && effectType && (
                <>
                  {viewMode !== 'user' && (
                    <TroubleshootButton virtual={virtual} />
                  )}
                  <TourEffect schemaProperties={orderedProperties} />
                  {/* <Button
                    onClick={() => handleRandomize()}
                    style={{ marginRight: '.5rem' }}
                    className={'step-device-six'}
                    >
                    <Casino />
                  </Button> */}
                  {virtual.config.rows > 1 && (
                    <Button
                      style={{ marginRight: '.5rem' }}
                      className="step-device-six"
                      onClick={() => setMatrix(!matrix)}
                    >
                      {matrix ? <GridOff /> : <GridOn />}
                    </Button>
                  )}
                  <Button
                    style={{ marginRight: '.5rem' }}
                    className="step-device-six"
                    onClick={() => handlePlayPause()}
                  >
                    {virtual.active ? <Pause /> : <PlayArrow />}
                  </Button>
                  <Button
                    className="step-device-five"
                    onClick={() => handleClearEffect()}
                  >
                    <Clear />
                  </Button>
                </>
              )}
            </div>
          </div>
          <Box
            sx={
              fade
                ? {
                    opacity: 0.2,
                    transition: 'opacity',
                    transitionDuration: '1000'
                  }
                : {
                    opacity: 1,
                    transitionDuration: '0'
                  }
            }
            style={{
              transitionDuration: `${
                (virtual?.config?.transition_time || 1) * 1000
              }`
            }}
          >
            <PixelGraph
              showMatrix={matrix}
              virtId={virtId}
              active={
                virtuals &&
                virtual &&
                effects &&
                virtual.effect &&
                virtual.effect.config
              }
              dummy={
                !(
                  virtuals &&
                  virtual &&
                  effects &&
                  virtual.effect &&
                  virtual.effect.config
                )
              }
            />
          </Box>
          <div style={{ height: '1rem' }} />
          <EffectDropDown
            effects={effects}
            virtual={virtual}
            features={features}
            getVirtuals={getVirtuals}
            setEffect={setEffect}
          />
        </CardContent>
      </Card>
      {virtuals &&
        virtual &&
        effects &&
        virtual.effect &&
        virtual.effect.config && (
          <Card variant="outlined" style={{ marginTop: '1rem' }}>
            <CardContent style={{ padding: '0 16px' }}>
              <Accordion
                style={{ padding: 0, boxShadow: 'none' }}
                defaultExpanded
                // defaultExpanded={viewMode !== 'user'}
              >
                <AccordionSummary
                  expandIcon={<ExpandMore />}
                  aria-controls="panel1a-content"
                  id="panel1a-header"
                  style={{ padding: 0 }}
                >
                  <Typography variant="h5">Effect Configuration</Typography>
                </AccordionSummary>
                <AccordionDetails style={{ padding: '0 0 8px 0' }}>
                  {theModel && effectType && (
                    <div>
                      <BladeEffectSchemaForm
                        handleEffectConfig={handleEffectConfig}
                        virtId={virtual.id}
                        schemaProperties={orderedProperties}
                        model={theModel as Record<string, unknown>}
                        selectedType={effectType}
                        descriptions={effectDescriptions}
                      />
                    </div>
                  )}
                </AccordionDetails>
              </Accordion>
            </CardContent>
          </Card>
        )}
    </>
  )
}

export default EffectsCard
