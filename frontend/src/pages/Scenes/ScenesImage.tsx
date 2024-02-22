import { useCallback, useEffect, useState } from 'react'
import isElectron from 'is-electron'
import { CardMedia } from '@mui/material'
import useStore from '../../store/useStore'
import useStyles from './Scenes.styles'
import BladeIcon from '../../components/Icons/BladeIcon/BladeIcon'

const SceneImage = ({ iconName }: { iconName: string }) => {
  const classes = useStyles()
  const [imageData, setImageData] = useState(null)
  const getImage = useStore((state) => state.getImage)
  const fetchImage = useCallback(async (ic: string) => {
    const result = await getImage(
      ic.split('image:')[1]?.replaceAll('file:///', '')
    )
    setImageData(result.image)
  }, [])
  useEffect(() => {
    if (iconName?.startsWith('image:')) {
      fetchImage(iconName)
    }
  }, [iconName, fetchImage])

  return iconName && iconName.startsWith('image:') ? (
    isElectron() ? (
      <CardMedia
        className={classes.media}
        image={iconName.split('image:')[1]}
        title="Contemplative Reptile"
      />
    ) : (
      <div
        className={classes.media}
        style={{
          height: 140,
          maxWidth: 'calc(100% - 2px)',
          backgroundSize: 'cover',
          backgroundImage: `url("data:image/png;base64,${imageData}")`
        }}
        title="SceneImage"
      />
    )
  ) : (
    <BladeIcon scene className={classes.iconMedia} name={iconName} />
  )
}

export default SceneImage
