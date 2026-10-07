Pod::Spec.new do |s|
  s.name = 'EPTVVLCKit'
  s.version = '4.0.0a25.eptv1'
  s.summary = 'EPTV Mac and TV build of VLCKit 4 with identified GPL components excluded.'
  s.homepage = 'https://code.videolan.org/videolan/VLCKit'
  s.authors = { 'VideoLAN and VLC contributors' => 'videolan@videolan.org' }
  s.license = { :type => 'LGPL-2.1-or-later', :file => 'COPYING' }
  s.source = { :http => 'https://github.com/crecotun/eptv-vlckit/releases/download/4.0.0a25.eptv1/EPTVVLCKit.zip' }
  s.module_name = 'VLCKit'
  s.osx.deployment_target = '26.0'
  s.tvos.deployment_target = '26.0'
  s.vendored_frameworks = 'VLCKit.xcframework'
  s.frameworks = 'Foundation'
  s.libraries = 'iconv'
  s.requires_arc = false
  s.preserve_paths = 'build-record.json', 'TransitiveNotices.txt'
end
