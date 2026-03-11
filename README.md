# NovaSM3

https://novaspotmicro.com/

<img width="2478" height="1553" alt="nova_photos" src="https://github.com/user-attachments/assets/72690bb9-d9ce-496c-8b56-ba216383a987" />

## STL File List 

<img width="1086" height="698" alt="011" src="https://github.com/user-attachments/assets/bb1de2ad-5a5c-4b5c-bd01-008ac398449e" />

 * SM3_CalibrationTool.stl						
 * SM3_Cover_BottomFront.stl					
 * SM3_Cover_BottomHatch.stl					
 * SM3_Cover_BottomRear.stl					
 * SM3_Cover_Emblem.stl						
 * SM3_Cover_HeadPanel.stl						
 * SM3_Cover_HeadPanelSlug.stl					
 * SM3_Cover_LeftFemur.stl						
 * SM3_Cover_RearPanelBtnHolder_6x6LongBtn.stl	
 * SM3_Cover_RearPanel_2Piece_Base.stl			
 * SM3_Cover_RearPanel_2Piece_Shell.stl		
 * SM3_Cover_RightFemur.stl					
 * SM3_Cover_TopFront.stl						
 * SM3_Cover_TopRear.stl						
 * SM3_Electronics_BuckConveterCase.stl		
 * SM3_Foot.stl									
 * SM3_Frame_ChassisTrunk.stl					
 * SM3_Frame_FrontShoulderInner.stl			
 * SM3_Frame_FrontShoulderMiddle.stl			
 * SM3_Frame_FrontShoulderOuter.stl			
 * SM3_Frame_LeftCoax.stl						
 * SM3_Frame_LeftFemur.stl						
 * SM3_Frame_LeftTibia.stl						
 * SM3_Frame_RearShoulderInner.stl				
 * SM3_Frame_RearShoulderMiddle.stl			
 * SM3_Frame_RearShoulderOuter.stl				
 * SM3_Frame_RightCoax.stl						
 * SM3_Frame_RightFemur.stl					
 * SM3_Frame_RightTibia.stl					
 * SM3_Mp3ProSpeakerMount.stl					
 * SM3_Sensor_FrontPIRMount.stl				
 * SM3_Sensor_MP3SpeakerMount.stl				
 * SM3_Sensor_PIRCup.stl						
 * SM3_Sensor_RearPIRMount.stl					
 * SM3_Sensor_UltraSonicPlate.stl				
 * SM3_Stand_Cone.stl							
 * SM3_Stand_ConeBase.stl						
 * SM3_Stand_ConeCap.stl									


## Stl Viewer
  * 현재 뷰어는 법선(Normal) 스무딩이 과해서 면이 뭉개져 보입니다. 에지를 선명하게 하려면 법선 분리각도 조정 + 엣지 라인 오버레이 를 추가하면 됩니다.3개의 파일 조회함, 명령 2개 실행함, 파일 읽음3개의 파일 조회함, 명령 2개 실행함, 파일 읽음수정 내용은 두 가지입니다.
① 법선 분리 각도 조정 (FeatureAngle = 30°)
기존에는 SplittingOff()로 모든 면을 부드럽게 보간해서 엣지가 뭉개졌습니다. 이제 30도 이상 꺾이는 면은 법선을 분리해서 날카로운 엣지로 렌더링합니다. Creality처럼 평면은 매끈하고 모서리는 선명하게 보입니다.
② 엣지 라인 오버레이
반투명 검정 와이어프레임을 표면 위에 얇게 덮어씌워 면과 면의 경계가 더 뚜렷하게 보이도록 했습니다. (와이어프레임 버튼 ON 시 자동으로 숨겨집니다)
