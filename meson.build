project('crowbar_programs', 'c',
  version : '0.1.0',
  default_options : ['warning_level=3', 'optimization=0'])

# Common source files included in every build
common_sources = files('allocator.c', 'custodian.c')

# Python crowbar code generator
py = find_program('python3', 'python')
crowbar_script = files('crowbar.py')

# Find libraries that might be needed
# m_dep = meson.get_compiler('c').find_library('m', required : false)
# pthread_dep = dependency('threads', required : false)
vfn = dependency('libvfn', required: true)

# Define your test programs with optional dependencies
# Format: [name, [list of dependencies]]
test_programs = [
  ['lol', [vfn]],
  #['math_test', [m_dep]],
  #['threaded_test', [pthread_dep, m_dep]],
]

foreach prog_info : test_programs
  prog = prog_info[0]
  prog_deps = prog_info[1]
  prog_c = prog + '.c'
  
  # Run crowbar.py code generator on the source file
  gen_target = custom_target(prog + '_gen',
    input : prog_c,
    output : prog + '_gen.stamp',
    command : [py, crowbar_script, '@INPUT@'],
    build_by_default : true
  )
  
  # Build the executable (depends on code generation)
  exe = executable(prog,
    [prog_c, gen_target],
    common_sources,
    c_args : ['-O0'],
    dependencies : prog_deps,
  )
  
  # Create a run target for convenience
  run_target(prog + '_run',
    command : [exe],
    depends : [exe]
  )
endforeach
