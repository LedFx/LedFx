import { useEffect } from 'react'
import useStore from '../../store/useStore'
import BladeSchemaForm from '../../components/SchemaForm/SchemaForm/SchemaForm'

const AudioCard = ({ className }: any) => {
  const setSystemConfig = useStore((state) => state.setSystemConfig)
  const getSystemConfig = useStore((state) => state.getSystemConfig)
  const schema = useStore((state) => state?.schemas?.audio?.schema)
  const model = useStore((state) => state?.config?.audio)

  useEffect(() => {
    getSystemConfig()
  }, [])

  return (
    <div className={className}>
      {schema && (
        <BladeSchemaForm
          hideToggle
          schema={schema}
          model={model}
          onModelChange={(e) => {
            setSystemConfig({
              audio: e
            }).then(() => getSystemConfig())
          }}
        />
      )}
    </div>
  )
}

export default AudioCard
