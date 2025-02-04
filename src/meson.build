pkgdatadir = join_paths(get_option('prefix'), get_option('datadir'), meson.project_name())
moduledir = join_paths(pkgdatadir, 'newelle')
gnome = import('gnome')

gnome.compile_resources('newelle',
  'newelle.gresource.xml',
  gresource_bundle: true,
  install: true,
  install_dir: pkgdatadir,
)

python = import('python')

conf = configuration_data()
conf.set('PYTHON', python.find_installation('python3').path())
conf.set('VERSION', meson.project_version())
conf.set('localedir', join_paths(get_option('prefix'), get_option('localedir')))
conf.set('pkgdatadir', pkgdatadir)

configure_file(
  input: 'newelle.in',
  output: 'newelle',
  configuration: conf,
  install: true,
  install_dir: get_option('bindir'),
  install_mode: 'r-xr--r--'
)

newelle_sources = [
  '__init__.py',
  'main.py',
  'constants.py',
  'window.py',
  'extensions.py',
]

ui_sources = [
  'ui/__init__.py',
  'ui/profile.py',
  'ui/extension.py',
  'ui/settings.py',
  'ui/presentation.py',
  'ui/thread_editing.py',
  'ui/screenrecorder.py',
  'ui/shortcuts.py',
  'ui/mini_window.py',
]

widgets_sources = [
  'ui/widgets/__init__.py',
  'ui/widgets/multiline.py',
  'ui/widgets/profilerow.py',
  'ui/widgets/barchart.py',
  'ui/widgets/comborow.py',
  'ui/widgets/copybox.py',
  'ui/widgets/file.py',
  'ui/widgets/latex.py',
]

handler_sources = [
  'handlers/__init__.py',
  'handlers/handler.py',
]

llm_sources = [
  'handlers/llm/__init__.py',
  'handlers/llm/llm.py',
  'handlers/llm/bing_handler.py',
  'handlers/llm/claude_handler.py',
  'handlers/llm/custom_handler.py',
  'handlers/llm/g4f_handler.py',
  'handlers/llm/gemini_handler.py',
  'handlers/llm/gpt3any_handler.py',
  'handlers/llm/gpt4all_handler.py',
  'handlers/llm/groq_handler.py',
  'handlers/llm/mistral_handler.py',
  'handlers/llm/newelle_handler.py',
  'handlers/llm/ollama_handler.py',
  'handlers/llm/openai_handler.py',
  'handlers/llm/openrouter_handler.py',
  'handlers/llm/deepseek_handler.py',
  ]

tts_sources = [
  'handlers/tts/__init__.py',
  'handlers/tts/tts.py',
  'handlers/tts/gtts_handler.py',
  'handlers/tts/espeak_handler.py',
  'handlers/tts/elevenlabs_handler.py',
  'handlers/tts/custom_handler.py',
]

stt_sources = [  
  'handlers/stt/__init__.py',
  'handlers/stt/stt.py',
  'handlers/stt/googlesr_handler.py',
  'handlers/stt/groqsr_handler.py',
  'handlers/stt/openaisr_handler.py',
  'handlers/stt/sphinx_handler.py',
  'handlers/stt/witai_handler.py',
  'handlers/stt/whisper_handler.py',
  'handlers/stt/custom_handler.py',
  'handlers/stt/vosk_handler.py',
]

utility_sources = [
  'utility/__init__.py',
  'utility/media.py',
  'utility/pip.py',
  'utility/replacehelper.py',
  'utility/strings.py',
  'utility/system.py',
  'utility/util.py',
  'utility/profile_settings.py',
  'utility/audio_recorder.py',
  'utility/message_chunk.py'
]

install_data(newelle_sources, install_dir: moduledir)
install_data(ui_sources, install_dir: moduledir / 'ui')
install_data(widgets_sources, install_dir: moduledir / 'ui' / 'widgets')
install_data(handler_sources, install_dir: moduledir / 'handlers')
install_data(llm_sources, install_dir: moduledir / 'handlers' / 'llm')
install_data(tts_sources, install_dir: moduledir / 'handlers' / 'tts')
install_data(stt_sources, install_dir: moduledir / 'handlers' / 'stt')
install_data(utility_sources, install_dir: moduledir / 'utility')

