import { useEffect, useState } from 'react'
import Box from '@mui/material/Box'
import {
  DataGrid,
  GridColDef,
  GridEventListener,
  GridRenderCellParams
} from '@mui/x-data-grid'
import { Card, CardMedia, Typography, useTheme } from '@mui/material'
import BladeIcon from '../../components/Icons/BladeIcon/BladeIcon'
import useStore from '../../store/useStore'

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
  { field: 'id', headerName: 'ID', width: 70 },
  {
    field: 'scene_image',
    headerName: 'Image',
    width: 150,
    renderCell: (params: GridRenderCellParams) =>
      sceneImage(params.value || 'Wallpaper', true)
  },
  {
    field: 'name',
    headerName: 'Name',
    width: 220
  },
  {
    field: 'used',
    type: 'number',
    headerName: 'Order',
    width: 20
  }
]

export default function ScenesRecent({ scenes, activateScene, title }: any) {
  const theme = useTheme()
  const recentScenes = useStore((state) => state.recentScenes)
  const [theScenes, setTheScenes] = useState({})
  const handleEvent: GridEventListener<'rowClick'> = (params) =>
    activateScene(
      Object.keys(scenes).find((s: any) => scenes[s].name === params.row?.name)
    )

  useEffect(() => {
    const current = {} as any
    recentScenes.map((key: string, i: number) => {
      current[key] = { ...scenes[key], used: i + 1 }
      return setTheScenes(current)
    })
  }, [scenes, recentScenes])

  return (
    <Card>
      <Box sx={{ height: 293, width: '100%', maxWidth: '470px', m: '0 auto' }}>
        <Typography
          color="GrayText"
          variant="h6"
          sx={{
            pl: 1,
            pt: 0.5,
            pb: 0.5,
            border: '1px solid',
            borderColor: theme.palette.divider,
            borderBottom: 0
          }}
        >
          {title}
        </Typography>
        <DataGrid
          onRowClick={handleEvent}
          rowHeight={50}
          columns={columns}
          hideFooter
          // headerHeight={1}
          pageSizeOptions={[5]}
          disableRowSelectionOnClick
          rows={Object.values(theScenes).map((v: any, i: number) => ({
            id: i + 1,
            ...v
          }))}
          initialState={{
            // pagination: {
            //   pageSize: 100,
            // },
            sorting: {
              sortModel: [{ field: 'used', sort: 'asc' }]
            },
            columns: {
              columnVisibilityModel: {
                id: false,
                scene_tags: false
              }
            }
          }}
          sx={{
            '&.MuiDataGrid-root .MuiDataGrid-cell:focus-within': {
              outline: 'none !important'
            }
          }}
        />
      </Box>
    </Card>
  )
}
