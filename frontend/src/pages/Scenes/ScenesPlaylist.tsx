import { useEffect, useState } from 'react'
import Box from '@mui/material/Box'
import { DataGrid, GridColDef, GridRenderCellParams } from '@mui/x-data-grid'
import {
  Button,
  Card,
  CardMedia,
  IconButton,
  TextField,
  Typography,
  useTheme
} from '@mui/material'
import {
  PlayArrow,
  PlaylistRemove,
  Repeat,
  RepeatOn,
  // Save,
  Stop
} from '@mui/icons-material'

import BladeIcon from '../../components/Icons/BladeIcon/BladeIcon'
import useStore from '../../store/useStore'
import ScenesPlaylistMenu from './ScenesPlaylistMenu'

export default function ScenesPlaylist({
  scenes,
  title,
  activateScene,
  db
}: any) {
  const theme = useTheme()
  const [theScenes, setTheScenes] = useState([])
  const scenePL = useStore((state) => state.scenePL)
  const scenePLplay = useStore((state) => state.scenePLplay)
  const toggleScenePLplay = useStore((state) => state.toggleScenePLplay)
  const scenePLrepeat = useStore((state) => state.scenePLrepeat)
  const toggleScenePLrepeat = useStore((state) => state.toggleScenePLrepeat)
  const scenePLactiveIndex = useStore((state) => state.scenePLactiveIndex)
  const scenePLinterval = useStore((state) => state.scenePLinterval)
  const setScenePLinterval = useStore((state) => state.setScenePLinterval)
  const setScenePLactiveIndex = useStore((state) => state.setScenePLactiveIndex)

  useEffect(() => {
    const current = scenePL.map((key: string, id: number) => ({
      id,
      ...scenes[key],
      scene_id: key
    }))
    return setTheScenes(current)
  }, [scenes, scenePL])

  let timer = null as any
  useEffect(() => {
    if (scenePLplay && timer === null) {
      timer = setTimeout(() => {
        if (scenePL[scenePLactiveIndex + 1])
          activateScene(scenePL[scenePLactiveIndex + 1])
        setScenePLactiveIndex(scenePLactiveIndex + 1)
      }, scenePLinterval * 1000)
    } else if (timer) {
      clearTimeout(timer)
    }
    return () => clearTimeout(timer)
  }, [scenePLplay, scenePLactiveIndex])

  useEffect(() => {
    if (scenePLplay && timer && scenePLactiveIndex >= theScenes.length) {
      if (scenePLrepeat) {
        activateScene(scenePL[0])
        setScenePLactiveIndex(0)
      } else {
        toggleScenePLplay()
        setScenePLactiveIndex(-1)
      }
    }
  }, [scenePLplay, scenePLactiveIndex])

  const sceneImage = (iconName: string, table?: boolean) =>
    iconName && iconName.startsWith('image:') ? (
      <CardMedia
        image={iconName.split('image:')[1]}
        title="Contemplative Reptile"
        sx={{ width: '100%', height: '100%' }}
      />
    ) : (
      <BladeIcon scene={!table} name={iconName} />
    )

  const columns: GridColDef[] = [
    { field: 'id', headerName: 'ID', width: 0 },
    {
      field: 'scene_image',
      headerName: 'Image',
      width: db ? 100 : 150,
      renderCell: (params: GridRenderCellParams) =>
        sceneImage(params.value || 'Wallpaper', true)
    },
    {
      field: 'name',
      headerName: 'Name',
      width: db ? 136 : 200,
      renderCell: (params: GridRenderCellParams) => (
        <Typography
          variant="body2"
          sx={{
            whiteSpace: 'nowrap',
            overflow: 'hidden',
            textOverflow: 'ellipsis'
          }}
        >
          {params.value}
        </Typography>
      )
    },
    {
      field: 'scene_id',
      headerName: 'Remove',
      width: 120,
      renderCell: (params: GridRenderCellParams) => {
        const removeScene2PL = useStore((state) => state.removeScene2PL)
        return (
          <Button
            onClick={() => removeScene2PL(params.id as number)}
            size="small"
            variant="text"
          >
            <PlaylistRemove />
          </Button>
        )
      }
    }
  ]

  return (
    <Card
      sx={{
        background: db ? 'transparent' : '',
        borderColor: db ? 'transparent' : ''
      }}
    >
      <Box
        sx={{
          height: db ? 301 : 293,
          width: '100%',
          maxWidth: '470px',
          m: '0 auto'
        }}
      >
        <Typography
          color="GrayText"
          variant="h6"
          sx={{
            pl: 1,
            pt: 0.5,
            pb: 0.5,
            border: '1px solid',
            borderColor: db ? 'transparent' : theme.palette.divider,
            borderBottom: 0,
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center'
          }}
        >
          {title}
          {!(window.localStorage.getItem('guestmode') === 'activated') && (
            <ScenesPlaylistMenu />
          )}
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              color: db ? theme.palette.text.primary : ''
            }}
          >
            {db ? (
              <IconButton
                sx={{ mr: 1 }}
                onClick={() => {
                  toggleScenePLrepeat()
                }}
              >
                {scenePLrepeat ? <RepeatOn /> : <Repeat />}
              </IconButton>
            ) : (
              <Button
                sx={{ mr: 1 }}
                onClick={() => {
                  toggleScenePLrepeat()
                }}
              >
                {scenePLrepeat ? <RepeatOn /> : <Repeat />}
              </Button>
            )}
            {db ? '' : 'sec'}
            <TextField
              variant="standard"
              sx={{
                width: 70,
                border: '1px solid',
                borderColor: theme.palette.divider,
                marginRight: 1,
                marginLeft: 1,
                borderRadius: 1,
                '& input': {
                  textAlign: 'right',
                  padding: '5px 0 2px'
                },
                '& .MuiInput-underline:before': {
                  display: 'none'
                },
                '& .MuiInput-underline:after': {
                  display: 'none'
                }
              }}
              type="number"
              value={scenePLinterval}
              onChange={(e: any) => setScenePLinterval(e.target.value)}
            />
            {db ? (
              <IconButton
                sx={{ mr: 1 }}
                onClick={() => {
                  if (scenePLplay) {
                    setScenePLactiveIndex(-1)
                  } else {
                    activateScene(scenePL[0])
                    setScenePLactiveIndex(0)
                  }
                  toggleScenePLplay()
                }}
              >
                {scenePLplay ? <Stop /> : <PlayArrow />}
              </IconButton>
            ) : (
              <Button
                sx={{ mr: 1 }}
                onClick={() => {
                  if (scenePLplay) {
                    setScenePLactiveIndex(-1)
                  } else {
                    activateScene(scenePL[0])
                    setScenePLactiveIndex(0)
                  }
                  toggleScenePLplay()
                }}
              >
                {scenePLplay ? <Stop /> : <PlayArrow />}
              </Button>
            )}
          </div>
        </Typography>

        <DataGrid
          rowHeight={50}
          columns={columns}
          hideFooter
          // headerHeight={1}
          // pageSize={5}
          disableRowSelectionOnClick
          rows={(
            (theScenes && theScenes.length > 0 && Object.values(theScenes)) ||
            []
          ).map((v: any, i: number) => ({
            id: i + 1,
            ...v
          }))}
          getRowClassName={(params) =>
            `row${params.row.id === scenePLactiveIndex ? '--active' : ''}`
          }
          pageSizeOptions={[100]}
          initialState={{
            sorting: {
              sortModel: [{ field: 'id', sort: 'asc' }]
            },
            columns: {
              columnVisibilityModel: {
                id: false,
                scene_tags: false
              }
            }
          }}
          sx={{
            borderColor: db ? 'transparent' : theme.palette.divider,
            '&.MuiDataGrid-root .MuiDataGrid-cell:focus-within': {
              outline: 'none !important'
            },
            '&.MuiDataGrid-root .row--active': {
              background: `${theme.palette.primary.main}30`
            }
          }}
        />
      </Box>
    </Card>
  )
}
